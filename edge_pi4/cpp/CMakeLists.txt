cmake_minimum_required(VERSION 3.10)
project(yolo11_ncnn)

# C++ Standard configuration
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find OpenCV package
find_package(OpenCV REQUIRED)

# Find OpenMP
find_package(OpenMP REQUIRED)

# Đọc biến môi trường HOME để định vị đường dẫn NCNN SDK cục bộ trên Raspberry Pi (đã sửa đường dẫn có thirdparty)
set(ncnn_DIR "$ENV{HOME}/yoloncnn/thirdparty/ncnn_build/install/lib/cmake/ncnn" CACHE PATH "Path to ncnn CMake config" FORCE)

# Find NCNN
find_package(ncnn REQUIRED)

# Source files
add_executable(yolo11_ncnn 
    src/main.cpp 
    src/yolo11.cpp
)

target_link_libraries(yolo11_ncnn 
    ${OpenCV_LIBS} 
    ncnn 
    OpenMP::OpenMP_CXX
)
