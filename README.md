# None Motor AI Guard
- [x] 学习 Visual Language Model，查找 API 并集成到 OpenCV；YOLOv8 的非机动车识别模型
- [ ] 解决目标追踪时ID频繁变化的问题
      1. 使用外观特征、位置信息或运动模式来关联不同ID。
         修改日志记录函数，将特征哈希、位置等信息包含进去。添加日志分析脚本，读取日志文件，按特征哈希分组，找出同一哈希对应的不同ID，从而识别可能的ID切换。
      2. 计算新目标和丢失目标的 IOU（重叠程度）,特征向量相似度匹配相似度较高的ID。尝试用 深度学习特征匹配（如 Siamese 网络）
- [ ] 学习 Restful API 和 FastAPI；
- [ ] 学习 Restful API、Vue 和 React（使用 Cloud3.7 编写前端代码）；
- [ ] 准备项目书；
- [ ] 准备 PPT。
