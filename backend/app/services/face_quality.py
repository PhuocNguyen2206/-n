"""Chỉ nhận khuôn mặt đủ rõ để làm căn cứ cho xe qua cổng.

MTCNN vẫn "thấy mặt" khi tay hoặc điện thoại che mất một nửa, nên có thấy mặt
chưa đủ. Khuôn mặt lớn nhất trong khung (người điều khiển xe) phải qua được cả
ngưỡng độ tin cậy và câu hỏi cho VLM. Xét mặt lớn nhất để một người đứng phía
sau không "qua hộ" người đang che mặt.
"""

from io import BytesIO

from PIL import Image

from .. import config

UNCLEAR_REASON = "Khuôn mặt chưa rõ: bỏ tay, khẩu trang hoặc vật che và nhìn thẳng vào camera"


def _area(face) -> float:
    box = getattr(face, "box", ())
    return (box[2] - box[0]) * (box[3] - box[1]) if box else 0.0


def _same_vehicle(face, main_face) -> bool:
    box, main_box = getattr(face, "box", ()), getattr(main_face, "box", ())
    return not box or not main_box or box[2] - box[0] >= config.FACE_MIN_RELATIVE_SIZE * (main_box[2] - main_box[0])


def _crop(image_data: bytes, box, margin: float = 0.35) -> Image.Image:
    """Cắt quanh khuôn mặt, chừa lề và phóng lên tối thiểu 448 px như lúc đo."""
    with Image.open(BytesIO(image_data)) as source:
        image = source.convert("RGB")
    left, top, right, bottom = box
    pad_x, pad_y = (right - left) * margin, (bottom - top) * margin
    face = image.crop((max(0, int(left - pad_x)), max(0, int(top - pad_y)),
                       min(image.width, int(right + pad_x)), min(image.height, int(bottom + pad_y))))
    if max(face.size) < 448:
        scale = 448 / max(face.size)
        face = face.resize((int(face.width * scale), int(face.height * scale)))
    return face


def clear_faces(image_data: bytes, faces: list, vlm=None) -> list:
    """Trả về các khuôn mặt dùng được trong khung; rỗng nếu người điều khiển xe chưa lộ rõ mặt."""
    if not faces:
        return []
    main_face = max(faces, key=lambda face: (_area(face), face.confidence))
    if main_face.confidence < config.FACE_MIN_CONFIDENCE:
        return []
    check = getattr(vlm, "check_face", None)
    # VLM tắt hoặc lỗi (None) thì dựa vào ngưỡng độ tin cậy, cổng vẫn hoạt động.
    if config.FACE_VLM_CHECK and check and getattr(main_face, "box", ()) and check(_crop(image_data, main_face.box)) is False:
        return []
    # Mặt nhỏ hơn hẳn người lái là người của xe phía sau: không được lưu hay so khớp cho xe này.
    return [face for face in faces if face.confidence >= config.FACE_MIN_CONFIDENCE and _same_vehicle(face, main_face)]
