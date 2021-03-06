cmake_minimum_required(VERSION 2.8.3)
project(detection_tree)

add_compile_options(-std=c++11)
set(OpenCV_DIR /usr/share/OpenCV)

find_package(catkin REQUIRED COMPONENTS
  darknet_ros_msgs
  geometry_msgs
  roscpp
  std_msgs
  nodelet
  tf
  sensor_msgs
  OpenCV
  cv_bridge
  detection_tree_msgs
)

catkin_python_setup()

catkin_package(
  LIBRARIES detection_tree_node
  CATKIN_DEPENDS nodelet roscpp
)

include_directories(
  include
  ${catkin_INCLUDE_DIRS}
)

add_library( detection_tree_node 
src/detection_tree_node.cpp )
target_link_libraries(detection_tree_node ${catkin_LIBRARIES})

# Multiplexer Node (no nodelet)
add_executable( detection_tree_node_no_nodelet
  src/detection_tree_node.cpp
)
add_dependencies(detection_tree_node_no_nodelet ${catkin_EXPORTED_TARGETS})
target_link_libraries(detection_tree_node_no_nodelet ${catkin_LIBRARIES})