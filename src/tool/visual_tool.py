import torch
from torchvision import transforms
from torchvision.utils import draw_bounding_boxes

def draw_img_bboxes_labels(image, bboxes, labels,resize_shape=[96,500],colors='red'):
    bboxes = torch.index_select(bboxes.cpu(),1,torch.tensor([1,0,3,2]))

    img_and_bbox = draw_bounding_boxes(image.cpu(),bboxes.cpu(),labels,width=2,colors=colors,font_size=40)
    transform = transforms.Compose([transforms.Resize(resize_shape),transforms.RandomInvert(1.0)])
    img_and_bbox = transform(img_and_bbox)
    return img_and_bbox