cmake_minimum_required(VERSION 2.8.3)
project(localizer)
add_compile_options(-std=c++11)

set(OpenCV_DIR /usr/share/OpenCV)

find_package(catkin REQUIRED COMPONENTS
  nodelet
  roscpp
  OpenCV
  darknet_ros_msgs
  sensor_msgs
  cv_bridge
  image_transport
  geometry_msgs
  std_msgs
  tf
  localizer_msgs
)

catkin_package(
  LIBRARIES localizer
  CATKIN_DEPENDS cv_bridge image_transport nodelet roscpp sensor_msgs std_msgs
)
include_directories(include ${catkin_INCLUDE_DIRS})
add_library( localizer
  src/localizer.cpp
  src/pose_generator.cpp
  src/start_gate_hough.cpp
  src/jiangshi_watershed.cpp
  src/z_plane.cpp
)

if(catkin_EXPORTED_LIBRARIES)
add_dependencies(localizer ${catkin_EXPORTED_LIBRARIES})
endif()

add_dependencies(localizer ${catkin_EXPORTED_TARGETS})

target_link_libraries(localizer ${catkin_LIBRARIES})

# Localizer Node (no nodelet)
add_executable( localizer_node
  src/localizer.cpp
  src/pose_generator.cpp
  src/z_plane.cpp
)
add_dependencies(localizer_node ${catkin_EXPORTED_TARGETS})
target_link_libraries(localizer_node ${catkin_LIBRARIES})

# Test files

add_executable( start_gate_unit 
  unit_tests/start_gate_hough_test.cpp
  src/pose_generator.cpp
  src/start_gate_hough.cpp
)
add_dependencies(start_gate_unit ${catkin_EXPORTED_TARGETS})
target_link_libraries(start_gate_unit ${catkin_LIBRARIES})

add_executable( jiangshi_unit 
  unit_tests/jiangshi_watershed_test.cpp
  src/pose_generator.cpp
  src/jiangshi_watershed.cpp
)
add_dependencies(jiangshi_unit ${catkin_EXPORTED_TARGETS})
target_link_libraries(jiangshi_unit ${catkin_LIBRARIES})
