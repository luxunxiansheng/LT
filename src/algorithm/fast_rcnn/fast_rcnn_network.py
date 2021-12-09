import torch
import torch.nn as nn
from torchvision.ops import RoIPool

from common import FCBlock, weights_normal_init

class FastRCNN(nn.Module):
    def __init__(self, config):
        # n_class includes the background
        super().__init__()
    
        self.roi_pool = RoIPool((config.FAST_RCNN.ROI_SIZE,config.FAST_RCNN.ROI_SIZE),config.FAST_RCNN.SPATIAL_SCALE)

        self.fc6 = FCBlock(config.FAST_RCNN.IN_CHANNELS*config.FAST_RCNN.ROI_SIZE*config.FAST_RCNN.ROI_SIZE,
                        config.FAST_RCNN.FC7_CHANNELS)
        self.fc7 = FCBlock(config.FAST_RCNN.FC7_CHANNELS, config.FAST_RCNN.FC7_CHANNELS)
        
        self.loc = nn.Linear(config.FAST_RCNN.FC7_CHANNELS,  (config.FAST_RCNN.NUM_CLASSES+1) * 4)
        self.score = nn.Linear(config.FAST_RCNN.FC7_CHANNELS,config.FAST_RCNN.NUM_CLASSES+1)

        weights_normal_init(self.loc, 0.001)
        weights_normal_init(self.score,0.01)

    def forward(self,feature,rois,roi_indices):
        indices_and_rois = torch.cat([roi_indices[:, None], rois], dim=1)
        indices_and_rois = indices_and_rois[:, [0, 2, 1, 4, 3]]
        indices_and_rois = indices_and_rois.contiguous()

        pool = self.roi_pool(feature, indices_and_rois)
        pool = pool.view(pool.size(0), -1)
        fc6 = self.fc6(pool)
        fc7 = self.fc7(fc6)
        roi_cls_locs = self.loc(fc7)
        roi_scores = self.score(fc7)

        return roi_cls_locs, roi_scores
