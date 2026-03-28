#include "scara_mtc/solution_executor.hpp"
#include <moveit_msgs/msg/robot_trajectory.hpp>
#include <moveit_task_constructor_msgs/msg/solution.hpp>

SolutionExecutor::SolutionExecutor(rclcpp::Node::SharedPtr node, const std::string& controller_name)
  : node_(node)
{
  client_ = rclcpp_action::create_client<control_msgs::action::FollowJointTrajectory>(
    node, controller_name + "/follow_joint_trajectory");
}

void SolutionExecutor::execute(const moveit::task_constructor::SolutionBase& solution)
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

control_msgs::action::FollowJointTrajectory::Goal 
SolutionExecutor::processTrajectory(const moveit::task_constructor::SolutionBase& solution)
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

      // Fix for "strictly increasing time" error
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
