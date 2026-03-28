#include <rclcpp/rclcpp.hpp>
#include "scara_mtc/solution_executor.hpp"

#include <moveit/task_constructor/task.h>
#include <moveit/task_constructor/stages/current_state.h>
#include <moveit/task_constructor/stages/move_to.h>
#include <moveit/task_constructor/stages/move_relative.h>
#include <moveit/task_constructor/solvers/pipeline_planner.h>
#include <moveit/task_constructor/solvers/cartesian_path.h>
#include <geometry_msgs/msg/vector3_stamped.hpp>

namespace mtc = moveit::task_constructor;

class ScaraTaskNode : public rclcpp::Node
{
public:
  ScaraTaskNode() : Node("scara_mtc_node")
  {
    declare_parameter<std::string>("arm_group", "scara_arm");
    arm_group_ = get_parameter("arm_group").as_string();

    timer_ = create_wall_timer(std::chrono::seconds(1), [this](){
      timer_->cancel();
      deferredInitAndRun();
    });
  }

private:
  void deferredInitAndRun()
  {
    RCLCPP_INFO(get_logger(), "Initializing MTC components...");

    executor_ = std::make_shared<SolutionExecutor>(shared_from_this(), "scara_controller");

    task_ = std::make_shared<mtc::Task>("scara_demo");
    task_->loadRobotModel(shared_from_this());

    sampling_planner_ = std::make_shared<mtc::solvers::PipelinePlanner>(shared_from_this());
    sampling_planner_->setPlannerId("ompl", "RRTConnectkConfigDefault");
    
    cartesian_planner_ = std::make_shared<mtc::solvers::CartesianPath>();
    cartesian_planner_->setMaxVelocityScalingFactor(0.5);
    cartesian_planner_->setStepSize(0.01);

    planAndRun();
  }

  void planAndRun()
  {
    setupTask();

    RCLCPP_INFO(get_logger(), "Planning...");
    if (task_->plan(1)) {
      RCLCPP_INFO(get_logger(), "Planning OK. Executing...");
      task_->introspection().publishSolution(*task_->solutions().front());
      executor_->execute(*task_->solutions().front());
    } else {
      RCLCPP_ERROR(get_logger(), "Planning Failed!");
    }
  }

  // --- Helpers ---

  // Универсальный MoveTo (XYZ) с отключенной строгостью ориентации
  std::unique_ptr<mtc::stages::MoveTo> createMoveToXYZ(const std::string& name, double x, double y, double z) {
      auto stage = std::make_unique<mtc::stages::MoveTo>(name, sampling_planner_);
      stage->setGroup(arm_group_);
      stage->setIKFrame("tool0");
      
      // --- ИСПРАВЛЕНИЕ ПАРАДОКСА ---
      // IK нашел решение по позиции (благодаря position_only_ik),
      // но у этого решения будет какой-то случайный угол поворота (Yaw).
      // Мы должны сказать MTC: "Принимай ЛЮБОЙ угол, который получился".
      stage->setProperty("goal_orientation_tolerance", 6.28); // 2 * PI (полный круг)
      
      geometry_msgs::msg::PoseStamped pose;
      pose.header.frame_id = "world";
      pose.pose.position.x = x; 
      pose.pose.position.y = y; 
      pose.pose.position.z = z;
      
      // Ориентация формальная (чтобы заполнить сообщение)
      pose.pose.orientation.w = 1.0; 
      pose.pose.orientation.x = 0.0;
      pose.pose.orientation.y = 0.0;
      pose.pose.orientation.z = 0.0;
      
      stage->setGoal(pose);
      return stage;
    }

  std::unique_ptr<mtc::stages::MoveTo> createMoveToNamed(const std::string& name, const std::string& target) {
    auto stage = std::make_unique<mtc::stages::MoveTo>(name, sampling_planner_);
    stage->setGroup(arm_group_);
    stage->setGoal(target);
    return stage;
  }

  std::unique_ptr<mtc::stages::MoveRelative> createLinearMove(const std::string& name, double z_offset) {
    auto stage = std::make_unique<mtc::stages::MoveRelative>(name, cartesian_planner_);
    stage->setGroup(arm_group_);
    stage->setIKFrame("tool0");
    
    geometry_msgs::msg::Vector3Stamped vec;
    vec.header.frame_id = "world";
    vec.vector.z = z_offset;
    stage->setDirection(vec);
    return stage;
  }

  void setupTask()
  {
    task_->clear();
    task_->setProperty("group", arm_group_);
    task_->setProperty("eef", "scara_ee");
    task_->setProperty("ik_frame", "tool0");

    task_->add(std::make_unique<mtc::stages::CurrentState>("current"));

    task_->add(createMoveToNamed("home", "home"));

    // --- 1. PICK (XYZ) ---
    {
      // Используем проверенную безопасную высоту 0.10 (середина хода)
      auto stage = createMoveToXYZ("pre-pick", 0.25, 0.0, 0.10);
      task_->add(std::move(stage));
    }
    task_->add(createLinearMove("approach", -0.04)); // Вниз 4 см
    task_->add(createLinearMove("retreat",   0.04)); // Вверх 4 см

    // --- 2. PLACE (XYZ) ---
    {
      // Другая точка (Y=0.25)
      auto stage = createMoveToXYZ("pre-place", 0.0, 0.25, 0.10);
      task_->add(std::move(stage));
    }
    task_->add(createLinearMove("place down", -0.04));
    task_->add(createLinearMove("place up",    0.04));

    task_->add(createMoveToNamed("return home", "home"));
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
