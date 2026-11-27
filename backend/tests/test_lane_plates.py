"""Chọn biển số của xe gần cổng nhất khi khung hình có nhiều xe."""

from app.services.vision import ObjectDetection, plates_by_distance


def plate(box, confidence=0.9):
    return ObjectDetection(label="license_plate", confidence=confidence, box=box)


def test_nearest_plate_comes_first_even_when_detector_is_surer_of_the_far_one():
    near, far = plate([0, 0, 200, 120], 0.7), plate([300, 0, 380, 50], 0.95)
    assert plates_by_distance([far, near]) == [near, far]


def test_double_detection_of_one_plate_counts_once_and_weak_boxes_are_ignored():
    whole, again, noise = plate([0, 0, 100, 60], 0.9), plate([5, 3, 98, 58], 0.8), plate([200, 0, 500, 200], 0.36)
    assert plates_by_distance([whole, again, noise]) == [whole]
    assert plates_by_distance([noise]) == [noise]
