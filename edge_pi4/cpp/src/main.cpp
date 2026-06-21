#include <iostream>
#include <chrono>
#include <opencv2/core/core.hpp>
#include <opencv2/highgui/highgui.hpp>
#include <opencv2/imgproc/imgproc.hpp>
#include "yolo11.h"

int main(int argc, char** argv) {
    if (argc < 4) {
        std::cout << "Usage: " << argv[0] << " [image_path] [model_param_path] [model_bin_path] (use_int8: 0 or 1)" << std::endl;
        std::cout << "Example: " << argv[0] << " test.jpg model.param model.bin 0" << std::endl;
        return -1;
    }

    std::string image_path = argv[1];
    std::string param_path = argv[2];
    std::string bin_path = argv[3];
    bool use_int8 = false;
    
    if (argc >= 5) {
        use_int8 = (std::stoi(argv[4]) == 1);
    }

    // Read image using OpenCV
    cv::Mat img = cv::imread(image_path, cv::IMREAD_COLOR);
    if (img.empty()) {
        std::cerr << "Failed to read image: " << image_path << std::endl;
        return -1;
    }

    // Initialize YOLOv11 NCNN Detector
    YOLO11 detector;
    if (detector.load(param_path, bin_path, use_int8) != 0) {
        std::cerr << "Failed to load model!" << std::endl;
        return -1;
    }

    // Run inference multiple times to measure warmup vs steady-state latency
    std::vector<Object> objects;
    
    std::cout << "[INFO] Running 10 iterations of inference to measure performance..." << std::endl;
    double total_latency_excluding_first = 0.0;
    
    for (int i = 0; i < 10; i++) {
        auto start_time = std::chrono::high_resolution_clock::now();
        
        detector.detect(img, objects, 0.25f, 0.45f);
        
        auto end_time = std::chrono::high_resolution_clock::now();
        std::chrono::duration<double, std::milli> latency = end_time - start_time;
        
        std::cout << "  -> Iteration " << i + 1 << ": " << latency.count() << " ms" << std::endl;
        
        if (i > 0) {
            total_latency_excluding_first += latency.count();
        }
    }

    double avg_latency = total_latency_excluding_first / 9.0;
    std::cout << "\n[SUMMARY] Warmup/Shader Compilation (Iteration 1): ~" << std::endl; 
    std::cout << "[SUMMARY] Steady-state Latency (Average of Iterations 2-10): " << avg_latency << " ms" << std::endl;
    std::cout << "[SUMMARY] Steady-state Frame Rate (FPS): " << (1000.0 / avg_latency) << " FPS" << std::endl;
    std::cout << "[INFO] Found " << objects.size() << " objects." << std::endl;

    // Draw and save result
    detector.draw(img, objects);
    
    std::string output_path = "output.jpg";
    cv::imwrite(output_path, img);
    std::cout << "[SUCCESS] Saved annotated image to: " << output_path << std::endl;

    return 0;
}
