import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.nn.modules.module import T

from rpn.anchor_creator import AnchorCreator
from rpn.anchor_target_creator import AnchorTargetCreator

class RPNLoss(nn.Module):
    """calculate the loss for a single image"""
    def __init__(self,config,device='cpu'):
        super().__init__()
        self.sigma = config.RPN.RPN_SIGMA
        self.device = device

        self.anchor_target_creator = AnchorTargetCreator(config,device=device)

    def forward(self,anchors_of_img,predicted_scores,predicted_locs,target_bboxs,img_height,img_width):
        
        target_labels,target_locs = self.anchor_target_creator.create(anchors_of_img,target_bboxs,img_height,img_width)

        if target_labels is None:
            return torch.tensor(0.0,device=self.device),torch.tensor(0.0,device=self.device)

        # we only concern those anchors which have positive labels and negative labels
        target_keep =  target_labels.ne(-1).nonzero().squeeze()

        #----------------------- classfication loss -----------------------#
        predicted_scores = predicted_scores.permute(1,2,0).contiguous().view(-1,2)
        predicted_scores_keep = torch.index_select(predicted_scores,0,target_keep)
        target_labels_keep = torch.index_select(target_labels,0,target_keep) 
        classification_loss = F.cross_entropy(predicted_scores_keep,target_labels_keep.long(),ignore_index=-1)

        #----------------------- regression loss --------------------------#
        inside_weight = torch.zeros(target_locs.shape,device=self.device)

        # get the positive locs predicted by the network
        inside_weight[(target_labels > 0).view(-1,1).expand_as(inside_weight)] = 1
        predicted_locs = predicted_locs.permute(1,2,0).contiguous().view(-1,4)

        predicted_locs = inside_weight * predicted_locs
        target_locs = inside_weight * target_locs

        # loc_loss is the sum of the smooth L1 loss of the four coordinates of the positive anchors
        loc_loss = self._soomth_l1_loss(predicted_locs,target_locs,self.sigma)

        # Normalize by the number of the  positives
        regression_loss = loc_loss/((target_labels>=0).sum().float())  

        return classification_loss,regression_loss

    def compute(self,anchors_of_img,predicted_scores,predicted_locs,target_bboxs,img_height,img_width):
        return self.forward(anchors_of_img,predicted_scores,predicted_locs,target_bboxs,img_height,img_width)
    
    def _soomth_l1_loss(self, predicted_locs, target_locs,sigma):
        sigma2 = sigma**2
        diff = predicted_locs - target_locs
        abs_diff = diff.abs()
        flag = (abs_diff.data < (1.0 / sigma2)).float()
        loss = flag * (sigma2 / 2.) * (diff ** 2) +(1 - flag) * (abs_diff - 0.5 / sigma2)
        return loss.sum() 

