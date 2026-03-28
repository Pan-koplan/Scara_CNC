#pragma once

#include <rclcpp/rclcpp.hpp>
#include <rclcpp_action/rclcpp_action.hpp>
#include <control_msgs/action/follow_joint_trajectory.hpp>
#include <moveit/task_constructor/task.h>

// Объявляем класс, но не пишем здесь сложный код
class SolutionExecutor
{
public:
  SolutionExecutor(rclcpp::Node::SharedPtr node, const std::string& controller_name);

  void execute(const moveit::task_constructor::SolutionBase& solution);

private:
  control_msgs::action::FollowJointTrajectory::Goal processTrajectory(const moveit::task_constructor::SolutionBase& solution);

  rclcpp::Node::SharedPtr node_;
  rclcpp_action::Client<control_msgs::action::FollowJointTrajectory>::SharedPtr client_;
};
