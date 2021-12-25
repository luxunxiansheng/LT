# #### BEGIN LICENSE BLOCK #####
# Version: MPL 1.1/GPL 2.0/LGPL 2.1
#
# The contents of this file are subject to the Mozilla Public License Version
# 1.1 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# for the specific language governing rights and limitations under the
# License.
#
#
# Contributor(s):
#
#    Bin.Li (ornot2008@yahoo.com)
#
#
# Alternatively, the contents of this file may be used under the terms of
# either the GNU General Public License Version 2 or later (the "GPL"), or
# the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
# in which case the provisions of the GPL or the LGPL are applicable instead
# of those above. If you wish to allow use of your version of this file only
# under the terms of either the GPL or the LGPL, and not to allow others to
# use your version of this file under the terms of the MPL, indicate your
# decision by deleting the provisions above and replace them with the notice
# and other provisions required by the GPL or the LGPL. If you do not delete
# the provisions above, a recipient may use your version of this file under
# the terms of any one of the MPL, the GPL or the LGPL.
#
# #### END LICENSE BLOCK #####
#
# /


import torch
from torch.types import Device    
from torchvision.ops import box_iou
from yacs.config import CfgNode
from location_utility import LocationUtility

class AnchorTargetCreator:
    """Assign the ground truth bounding boxes to anchors."""
    def __init__(self,config:CfgNode,device:Device='cpu'):
        
        self.n_samples =      config.RPN.ANCHOR_TARGET_CREATOR.N_SAMPLES
        self.pos_iou_thresh = config.RPN.ANCHOR_TARGET_CREATOR.POSITIVE_IOU_THRESHOLD
        self.neg_iou_thresh = config.RPN.ANCHOR_TARGET_CREATOR.NEGATIVE_IOU_THRESHOLD
        self.pos_ratio =      config.RPN.ANCHOR_TARGET_CREATOR.POSITIVE_RATIO
        self.device =         device

    def create(self, 
            anchors_of_image:torch.Tensor,
            gt_bboxs:torch.Tensor,
            img_H:int,
            img_W:int)->torch.Tensor:
        """Generate the labels and the target regression values.
        
        Args:
            anchors_of_image: (N,4) tensor, the anchors of the image.
            gt_bboxs: (M,4) tensor, the ground truth bounding boxes.
            img_H: int the height of the image.
            img_W: int the width of the image.

        Returns:
            labels: (N,), the labels of the anchors.
            offsets: (N,4) tensor, the offsets of the anchors.
        """
        num_anchors_of_img = len(anchors_of_image)

        # get the index of anchors  inside the image
        valid_indices = self._get_inside_indices(anchors_of_image, img_H, img_W)

        if len(valid_indices) == 0:
            return None,None

        # get the anchors inside the image
        valid_anchors = anchors_of_image[valid_indices]

        # create labels for those valid anchors (inside the image). For tranning efficence, 
        # we only sample n_samples*pos_ratio positive anchors and n_smaples*(1-pos_ratio)
        # negative anchors.
    
        # label: 1 is positive, 0 is negative, -1 is dont care
        labels_for_valid_anchor = torch.empty((len(valid_indices),), dtype=torch.int32,device=self.device)
        labels_for_valid_anchor.fill_(-1)
        
        argmax_ious_for_valid_anchor, max_ious_for_valid_anchor, argmax_ious_for_gt_box = self._calc_ious(valid_anchors,gt_bboxs)
        
        # Assign negitive label (0) to all the anchor boxes which have max_iou less than negitive threshold 
        labels_for_valid_anchor[max_ious_for_valid_anchor < self.neg_iou_thresh] = 0

        # Assign positive label (1) to all the anchor boxes which have highest IoU overlap with a ground-truth box
        labels_for_valid_anchor[argmax_ious_for_gt_box] = 1

        # Assign positive label (1) to all the anchor boxes which have max_iou greater than positive threshold [b]
        labels_for_valid_anchor[max_ious_for_valid_anchor >= self.pos_iou_thresh] = 1

        # subsample positive labels if we have too many
        n_positive = int(self.pos_ratio * self.n_samples)
        positive_index = torch.where(labels_for_valid_anchor == 1)[0]

        if len(positive_index) > n_positive:
            disable_index = torch.multinomial(positive_index.float(),num_samples=(len(positive_index) - n_positive), replacement=False)
            disabled_positive_index = positive_index[disable_index]
            labels_for_valid_anchor[disabled_positive_index] = -1

        # subsample negative labels if we have too many
        n_negative = self.n_samples - torch.sum(labels_for_valid_anchor == 1)
        negative_index = torch.where(labels_for_valid_anchor == 0)[0]
        if len(negative_index) > n_negative:
            disable_index = torch.multinomial(negative_index.float(),num_samples=(len(negative_index) - n_negative), replacement=False)
            disabled_negative_index = negative_index[disable_index]
            labels_for_valid_anchor[disabled_negative_index] = -1

        # compute bounding box regression targets
        # Note, we will compute the regression targets for all the anchors inside the image 
        # irrespective of its label. 
        valid_offsets = LocationUtility.bbox2offset(valid_anchors, gt_bboxs[argmax_ious_for_valid_anchor])

        # map up to original set of anchors
        labels = self._unmap(labels_for_valid_anchor, num_anchors_of_img, valid_indices, fill=-1)
        offsets = self._unmap(valid_offsets, num_anchors_of_img, valid_indices, fill=0)
        
        return labels,offsets 
    
    def _calc_ious(self, 
                anchors:torch.Tensor,
                gt_bboxs:torch.Tensor)->torch.Tensor:

        """Calculate the IoU of anchors with ground truth boxes.
        
        Args:
            anchors: (N,4) tensor, the anchors of the image.
            gt_bboxs: (M,4) tensor, the ground truth bounding boxes.
        
        Returns:
            argmax_ious_for_anchor: (N,) tensor, the index of the ground truth box with highest IoU overlap with the anchor. 
            max_ious_for_anchor: (N,) tensor, the IoU of the anchor with the ground truth box with highest IoU overlap.
            argmax_ious_for_gt_box: (M,) tensor, the index of the anchor with highest IoU overlap with the ground truth box.              
        """
        # ious between the anchors and the gt boxes
        ious = box_iou(anchors, gt_bboxs)

        # for each gt box, find the anchor with the highest iou
        max_ious_for_gt_box,argmax_ious_for_gt_box = ious.max(dim=0)

        # for each gt box, there mihgt be multiple anchors with the same highest iou
        argmax_ious_for_gt_box = torch.where(ious == max_ious_for_gt_box)[0]

        # for each anchor, find the gt box with the highest iou
        max_ious_for_anchor,argmax_ious_for_anchor = ious.max(dim=1)
        
        return argmax_ious_for_anchor, max_ious_for_anchor, argmax_ious_for_gt_box

    @staticmethod
    def _get_inside_indices(anchors:torch.Tensor, img_H:int, img_W:int)->torch.Tensor:
                            
        """Calc indicies of anchors which are located completely inside of the image
        whose size is speficied.
        
        Args:
            anchors: (N,4) tensor, all the anchors of the image.
            img_H: int the height of the image.
            img_W: int the width of the image.
        
        Returns:
            indices: (N,) tensor, the indices of the anchors which are located completely inside of the image.

        """
        indices_inside = torch.where(
            (anchors[:, 0] >= 0) &
            (anchors[:, 1] >= 0) &
            (anchors[:, 2] <= img_H) &
            (anchors[:, 3] <= img_W)
        )[0]
        
        return indices_inside


    def _unmap(self,
            data:torch.Tensor, 
            count:int, 
            index:torch.Tensor,
            fill:int=0):

        """Unmap a subset of item (data) back to the original set of items (of size count)
        
        Args:
            data: (N,) tensor, the subset of data to unmap.
            count: int, the size of the original set of items.
            index: (N,) tensor, the indices of the subset of data to unmap.
            fill: the value to fill the unmapped item with.
        
        Returns:
            ret: (count,) or (count,4) tensor, the original set of items.
        """

        if len(data.shape) == 1:
            ret = torch.empty((count,), dtype=data.dtype,device=self.device)
            ret.fill_(fill)
            ret[index] = data
        else:
            ret = torch.empty((count,) + data.shape[1:], dtype=data.dtype,device=self.device)
            ret.fill_(fill)
            ret[index, :] = data
        return ret