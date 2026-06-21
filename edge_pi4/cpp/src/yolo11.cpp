#include "yolo11.h"
#include <iostream>
#include <opencv2/imgproc/imgproc.hpp>
#include <opencv2/highgui/highgui.hpp>

// NCNN options & layers
#include "net.h"
#include "layer.h"

static inline float intersection_area(const Object& a, const Object& b) {
    cv::Rect_<float> inter = a.rect & b.rect;
    return inter.area();
}

static void qsort_descent_inplace(std::vector<Object>& faceobjects, int left, int right) {
    int i = left;
    int j = right;
    float p = faceobjects[(left + right) / 2].prob;

    while (i <= j) {
        while (faceobjects[i].prob > p) i++;
        while (faceobjects[j].prob < p) j--;

        if (i <= j) {
            std::swap(faceobjects[i], faceobjects[j]);
            i++;
            j--;
        }
    }

    if (left < j) qsort_descent_inplace(faceobjects, left, j);
    if (i < right) qsort_descent_inplace(faceobjects, i, right);
}

static void qsort_descent_inplace(std::vector<Object>& faceobjects) {
    if (faceobjects.empty()) return;
    qsort_descent_inplace(faceobjects, 0, faceobjects.size() - 1);
}

static void nms_sorted_bboxes(const std::vector<Object>& faceobjects, std::vector<int>& picked, float nms_threshold) {
    picked.clear();
    const int n = faceobjects.size();

    std::vector<float> areas(n);
    for (int i = 0; i < n; i++) {
        areas[i] = faceobjects[i].rect.area();
    }

    for (int i = 0; i < n; i++) {
        const Object& a = faceobjects[i];
        int keep = 1;
        for (int j = 0; j < (int)picked.size(); j++) {
            const Object& b = faceobjects[picked[j]];

            float inter_area = intersection_area(a, b);
            float union_area = areas[i] + areas[picked[j]] - inter_area;
            if (inter_area / union_area > nms_threshold) {
                keep = 0;
            }
        }
        if (keep) {
            picked.push_back(i);
        }
    }
}

YOLO11::YOLO11() {}

YOLO11::~YOLO11() {
    net.clear();
}

int YOLO11::load(const std::string& param_path, const std::string& bin_path, bool use_int8) {
    net.clear();

    // Configure options for Raspberry Pi (OpenMP, ARM NEON, Vulkan GPU)
    net.opt.use_vulkan_compute = false;      // Disable Vulkan GPU on Pi 4 (since VideoCore VI lacks native FP16 arithmetic)
    net.opt.use_bf16_storage = true;         // Use BF16 for numerical stability
    net.opt.use_packing_layout = true;       // Enable packing layout for ARM NEON
    net.opt.num_threads = 4;                 // Use all 4 cores of Raspberry Pi

    // Configure INT8 quantization options if chosen
    if (use_int8) {
        net.opt.use_int8_inference = true;
        net.opt.use_fp16_arithmetic = false;
        std::cout << "[NCNN] INT8 Inference Mode Enabled!" << std::endl;
    } else {
        net.opt.use_fp16_arithmetic = true;  // Faster FP16 math on CPU/GPU
        std::cout << "[NCNN] FP16 Optimized Inference Mode Enabled!" << std::endl;
    }

    // Load model files
    if (net.load_param(param_path.c_str()) != 0) {
        std::cerr << "Failed to load param: " << param_path << std::endl;
        return -1;
    }
    if (net.load_model(bin_path.c_str()) != 0) {
        std::cerr << "Failed to load bin: " << bin_path << std::endl;
        return -1;
    }

    std::cout << "[NCNN] Model loaded successfully!" << std::endl;
    return 0;
}

int YOLO11::detect(const cv::Mat& bgr_img, std::vector<Object>& objects, float conf_threshold, float nms_threshold) {
    int img_w = bgr_img.cols;
    int img_h = bgr_img.rows;

    // 1. Preprocessing: Letterbox resizing keeping aspect ratio
    int w = img_w;
    int h = img_h;
    float scale = 1.f;
    if (w > h) {
        scale = (float)target_size / w;
        w = target_size;
        h = h * scale;
    } else {
        scale = (float)target_size / h;
        h = target_size;
        w = w * scale;
    }

    // Convert BGR Mat to NCNN Mat with resize
    ncnn::Mat in = ncnn::Mat::from_pixels_resize(
        bgr_img.data, ncnn::Mat::PIXEL_BGR2RGB, img_w, img_h, w, h
    );

    // Padding symmetrically to make target_size x target_size
    int wpad = target_size - w;
    int hpad = target_size - h;
    int top = hpad / 2;
    int bottom = hpad - top;
    int left = wpad / 2;
    int right = wpad - left;

    ncnn::Mat in_pad;
    ncnn::copy_make_border(
        in, in_pad, top, bottom, left, right, ncnn::BORDER_CONSTANT, 114.f
    );

    // Normalize pixel values to [0.0, 1.0]
    in_pad.substract_mean_normalize(0, norm_vals);

    // 2. Inference
    ncnn::Extractor ex = net.create_extractor();
    
    // In YOLO11, default input layer name is usually "in0" and output is "out0"
    ex.input("in0", in_pad);
    ncnn::Mat out0;
    ex.extract("out0", out0);

    // 3. Postprocessing: Parse YOLOv11 output tensor
    // Output head format: [1, 4 + num_classes, num_anchors]
    // In NCNN: out0.w = num_anchors, out0.h = 4 + num_classes
    int num_anchors = out0.w;
    int num_classes = out0.h - 4;

    std::vector<Object> proposal_objects;

    for (int i = 0; i < num_anchors; i++) {
        // Find class with the maximum confidence score
        float max_class_score = -1.f;
        int class_id = -1;

        for (int c = 0; c < num_classes; c++) {
            float class_score = out0.row(4 + c)[i];
            if (class_score > max_class_score) {
                max_class_score = class_score;
                class_id = c;
            }
        }

        if (max_class_score >= conf_threshold) {
            // Box coordinates (YOLO coordinates are center_x, center_y, width, height)
            float cx = out0.row(0)[i];
            float cy = out0.row(1)[i];
            float box_w = out0.row(2)[i];
            float box_h = out0.row(3)[i];

            // Convert center box coordinates to x1, y1, x2, y2
            float x1 = cx - box_w * 0.5f;
            float y1 = cy - box_h * 0.5f;

            // Store coordinates (bounding box is relative to the target_size padded image)
            Object obj;
            obj.rect.x = x1;
            obj.rect.y = y1;
            obj.rect.width = box_w;
            obj.rect.height = box_h;
            obj.label = class_id;
            obj.prob = max_class_score;

            proposal_objects.push_back(obj);
        }
    }

    // Sort proposals in descending order of confidence
    qsort_descent_inplace(proposal_objects);

    // Apply Non-Maximum Suppression (NMS)
    std::vector<int> picked;
    nms_sorted_bboxes(proposal_objects, picked, nms_threshold);

    int count = picked.size();
    objects.resize(count);

    for (int i = 0; i < count; i++) {
        objects[i] = proposal_objects[picked[i]];

        // Undo letterbox padding and scale back to original image size
        float x = (objects[i].rect.x - left) / scale;
        float y = (objects[i].rect.y - top) / scale;
        float box_w = objects[i].rect.width / scale;
        float box_h = objects[i].rect.height / scale;

        // Clip boxes to stay inside original image boundaries
        x = std::max(0.f, std::min(x, (float)(img_w - 1)));
        y = std::max(0.f, std::min(y, (float)(img_h - 1)));
        box_w = std::max(0.f, std::min(box_w, (float)(img_w - x - 1)));
        box_h = std::max(0.f, std::min(box_h, (float)(img_h - y - 1)));

        objects[i].rect.x = x;
        objects[i].rect.y = y;
        objects[i].rect.width = box_w;
        objects[i].rect.height = box_h;
    }

    return 0;
}

void YOLO11::draw(cv::Mat& bgr_img, const std::vector<Object>& objects) {
    for (size_t i = 0; i < objects.size(); i++) {
        const Object& obj = objects[i];

        // Unique colors for each class
        cv::Scalar color = cv::Scalar(0, 255, 0); // Green default
        if (obj.label == 1) color = cv::Scalar(255, 0, 0); // Blue for cars
        if (obj.label == 3) color = cv::Scalar(0, 0, 255); // Red for trucks

        // Draw bounding box
        cv::rectangle(bgr_img, obj.rect, color, 3);

        // Put text label and confidence score
        std::string label_str = class_names[obj.label] + " " + std::to_string((int)(obj.prob * 100)) + "%";
        
        int baseLine = 0;
        cv::Size label_size = cv::getTextSize(label_str, cv::FONT_HERSHEY_SIMPLEX, 0.6, 2, &baseLine);

        int x = obj.rect.x;
        int y = obj.rect.y - label_size.height - 5;
        if (y < 0) y = 0;
        if (x + label_size.width > bgr_img.cols) x = bgr_img.cols - label_size.width;

        cv::rectangle(bgr_img, cv::Rect(cv::Point(x, y), cv::Size(label_size.width, label_size.height + baseLine)), color, -1);
        cv::putText(bgr_img, label_str, cv::Point(x, y + label_size.height), cv::FONT_HERSHEY_SIMPLEX, 0.6, cv::Scalar(0, 0, 0), 2, cv::LINE_AA);
    }
}
