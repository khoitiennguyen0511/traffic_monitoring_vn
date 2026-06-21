#ifndef YOLO11_H
#define YOLO11_H

#include <string>
#include <vector>
#include <opencv2/core/core.hpp>
#include "net.h"

struct Object {
    cv::Rect_<float> rect;
    int label;
    float prob;
};

class YOLO11 {
public:
    YOLO11();
    ~YOLO11();

    // Load param & bin files, configure Vulkan and threads
    int load(const std::string& param_path, const std::string& bin_path, bool use_int8 = false);

    // Detect objects on the image
    int detect(const cv::Mat& bgr_img, std::vector<Object>& objects, float conf_threshold = 0.25f, float nms_threshold = 0.45f);

    // Draw detected bounding boxes on the frame
    void draw(cv::Mat& bgr_img, const std::vector<Object>& objects);

    // List of class names (configurable or default)
    std::vector<std::string> class_names = {"motorbike", "car", "bus", "truck", "bicycle"};

private:
    ncnn::Net net;
    int target_size = 480; // Default to 480 (as trained by user)
    float norm_vals[3] = {1/255.f, 1/255.f, 1/255.f};
};

#endif // YOLO11_H
