#include <rclcpp/rclcpp.hpp>
#include <rclcpp_action/rclcpp_action.hpp>

#include <moveit/task_constructor/task.h>
#include <moveit/task_constructor/stages/current_state.h>
#include <moveit/task_constructor/stages/move_to.h>
#include <moveit/task_constructor/stages/move_relative.h>
#include <moveit/task_constructor/solvers/pipeline_planner.h>
#include <moveit/task_constructor/solvers/cartesian_path.h>

// Сообщения
#include <control_msgs/action/follow_joint_trajectory.hpp>
#include <moveit_msgs/msg/robot_trajectory.hpp>
#include <moveit_task_constructor_msgs/msg/solution.hpp>
#include <geometry_msgs/msg/vector3_stamped.hpp>

namespace mtc = moveit::task_constructor;

// =========================================================================================
// 1. КЛАСС-ИСПОЛНИТЕЛЬ (Executor)
// Отвечает ТОЛЬКО за общение с контроллером (Action Client) и фильтрацию траектории.
// Скрывает всю "грязь" с таймингами и ros2_control.
// =========================================================================================
class SolutionExecutor
{
public:
  SolutionExecutor(rclcpp::Node::SharedPtr node, const std::string& controller_name)
    : node_(node)
  {
    client_ = rclcpp_action::create_client<control_msgs::action::FollowJointTrajectory>(
      node, controller_name + "/follow_joint_trajectory");
  }

  void execute(const mtc::SolutionBase& solution)
  {
    if (!client_->wait_for_action_server(std::chrono::seconds(3))) {
      RCLCPP_ERROR(node_->get_logger(), "Controller action server not found!");
      return;
    }

    auto goal_msg = processTrajectory(solution);
    
    RCLCPP_INFO(node_->get_logger(), "Sending trajectory (%zu points)...", goal_msg.trajectory.points.size());
    
    auto send_opts = rclcpp_action::Client<control_msgs::action::FollowJointTrajectory>::SendGoalOptions();
    send_opts.result_callback = [this](const auto & result) {
      if (result.code == rclcpp_action::ResultCode::SUCCEEDED) 
        RCLCPP_INFO(node_->get_logger(), "✅ Execution SUCCEEDED!");
      else 
        RCLCPP_ERROR(node_->get_logger(), "❌ Execution FAILED");
    };

    client_->async_send_goal(goal_msg, send_opts);
  }

private:
  control_msgs::action::FollowJointTrajectory::Goal processTrajectory(const mtc::SolutionBase& solution)
  {
    moveit_msgs::msg::RobotTrajectory full_traj;
    double time_offset = 0.0;
    
    moveit_task_constructor_msgs::msg::Solution solution_msg;
    solution.toMsg(solution_msg);

    for (const auto& sub_traj : solution_msg.sub_trajectory) {
      const auto& joint_traj = sub_traj.trajectory.joint_trajectory;
      if (joint_traj.points.empty()) continue;

      if (full_traj.joint_trajectory.joint_names.empty()) {
        full_traj.joint_trajectory.joint_names = joint_traj.joint_names;
      }

      for (auto point : joint_traj.points) {
        double t = rclcpp::Duration(point.time_from_start).seconds();
        double abs_t = t + time_offset;

        // Санитизация времени (защита от багов MTC/Controller)
        if (!full_traj.joint_trajectory.points.empty()) {
           double last_t = rclcpp::Duration(full_traj.joint_trajectory.points.back().time_from_start).seconds();
           if (abs_t <= last_t) abs_t = last_t + 0.001;
        }

        point.time_from_start = rclcpp::Duration::from_seconds(abs_t);
        full_traj.joint_trajectory.points.push_back(point);
      }
      
      if (!full_traj.joint_trajectory.points.empty()) {
        time_offset = rclcpp::Duration(full_traj.joint_trajectory.points.back().time_from_start).seconds();
      }
    }
    
    control_msgs::action::FollowJointTrajectory::Goal goal;
    goal.trajectory = full_traj.joint_trajectory;
    return goal;
  }

  rclcpp::Node::SharedPtr node_;
  rclcpp_action::Client<control_msgs::action::FollowJointTrajectory>::SharedPtr client_;
};

// =========================================================================================
// 2. ОСНОВНОЙ УЗЕЛ (Business Logic)
// Отвечает за логику задачи (Home -> Pick -> Place).
// Код чистый, читаемый, без лишних деталей.
// =========================================================================================
class ScaraTaskNode : public rclcpp::Node
{
public:
  ScaraTaskNode() : Node("scara_mtc_node")
  {
    // Параметры
    declare_parameter<std::string>("arm_group", "scara_arm");
    arm_group_ = get_parameter("arm_group").as_string();

    // Инициализация исполнителя
    executor_ = std::make_shared<SolutionExecutor>(shared_from_this(), "scara_controller");

    // Инициализация MTC таска
    task_ = std::make_shared<mtc::Task>("scara_demo");
    task_->loadRobotModel(shared_from_this());

    // Инициализация планировщиков
    sampling_planner_ = std::make_shared<mtc::solvers::PipelinePlanner>(shared_from_this());
    sampling_planner_->setPlannerId("ompl", "RRTConnectkConfigDefault");
    
    cartesian_planner_ = std::make_shared<mtc::solvers::CartesianPath>();
    cartesian_planner_->setMaxVelocityScalingFactor(0.5);
    cartesian_planner_->setStepSize(0.01);

    // Запуск через 2 сек
    timer_ = create_wall_timer(std::chrono::seconds(2), [this](){
      timer_->cancel();
      planAndRun();
    });
  }

private:
  void planAndRun()
  {
    setupTask(); // Строим пайплайн

    RCLCPP_INFO(get_logger(), "Planning...");
    if (task_->plan(1)) {
      RCLCPP_INFO(get_logger(), "Planning OK. Executing...");
      task_->introspection().publishSolution(*task_->solutions().front());
      executor_->execute(*task_->solutions().front());
    } else {
      RCLCPP_ERROR(get_logger(), "Planning Failed!");
    }
  }

  void setupTask()
  {
    task_->clear();
    task_->setProperty("group", arm_group_);
    task_->setProperty("eef", "scara_ee");
    task_->setProperty("ik_frame", "tool0");

    // --- СЦЕНАРИЙ ---
    
    // 1. Старт
    task_->add(std::make_unique<mtc::stages::CurrentState>("current"));

    // 2. Домой
    task_->add(createMoveTo("home", "home"));

    // 3. Pick Sequence
    {
      auto stage = createMoveTo("pre-pick", 0.3, 0.0, 0.25);
      task_->add(std::move(stage));
    }
    task_->add(createLinearMove("approach", -0.15)); // Вниз
    task_->add(createLinearMove("retreat",   0.15)); // Вверх

    // 4. Place Sequence
    {
      auto stage = createMoveTo("pre-place", 0.0, 0.3, 0.25);
      task_->add(std::move(stage));
    }
    task_->add(createLinearMove("place down", -0.15)); // Вниз
    task_->add(createLinearMove("place up",    0.15)); // Вверх

    // 5. Конец
    task_->add(createMoveTo("return home", "home"));
  }

  // --- Helpers (Чтобы не дублировать код) ---

  // Движение по имени (OMPL)
  auto createMoveTo(const std::string& name, const std::string& target) {
    auto stage = std::make_unique<mtc::stages::MoveTo>(name, sampling_planner_);
    stage->setGroup(arm_group_);
    stage->setGoal(target);
    return stage;
  }

  // Движение по координатам (OMPL)
  auto createMoveTo(const std::string& name, double x, double y, double z) {
    auto stage = std::make_unique<mtc::stages::MoveTo>(name, sampling_planner_);
    stage->setGroup(arm_group_);
    stage->setIKFrame("tool0"); // Важно для Cartesian целей!
    
    geometry_msgs::msg::PoseStamped pose;
    pose.header.frame_id = "world";
    pose.pose.position.x = x; 
    pose.pose.position.y = y; 
    pose.pose.position.z = z;
    pose.pose.orientation.w = 1.0;
    stage->setGoal(pose);
    return stage;
  }

  // Линейное движение по Z (Cartesian)
  auto createLinearMove(const std::string& name, double z_offset) {
    auto stage = std::make_unique<mtc::stages::MoveRelative>(name, cartesian_planner_);
    stage->setGroup(arm_group_);
    stage->setIKFrame("tool0");
    
    geometry_msgs::msg::Vector3Stamped vec;
    vec.header.frame_id = "world";
    vec.vector.z = z_offset;
    stage->setDirection(vec);
    return stage;
  }

  std::string arm_group_;
  mtc::TaskPtr task_;
  mtc::solvers::PipelinePlannerPtr sampling_planner_;
  mtc::solvers::CartesianPathPtr cartesian_planner_;
  std::shared_ptr<SolutionExecutor> executor_;
  rclcpp::TimerBase::SharedPtr timer_;
};

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<ScaraTaskNode>();
  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}
