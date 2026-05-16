建图协议
开始建图服务
- 名称：/perception/mapping_service
- 类型：service
- 数据类型：naviai_localization_msgs/Mapping
string map_name  # 地图名字
float32 z_floor  # Z轴最低限制0.1
float32 z_ceil   # Z轴最高限制2
float32 resolution
int scene    # 工况（室内/室外/...）
    int32 CONDITION_INDOOR=0    #室内
    int32 CONDITION_OUTDOOR=1    #室外
---
bool success    # 结果
string message  # 返回消息
建图反馈发布接口（全量）
- 名称：/projected_map
- 类型：topic/pub
- 数据类型：nav_msgs/OccupancyGrid
std_msgs/Header header
  uint32 seq
  time stamp
  string frame_id
nav_msgs/MapMetaData info
  time map_load_time
  float32 resolution
  uint32 width
  uint32 height
  geometry_msgs/Pose origin
    geometry_msgs/Point position #地图左下角坐标
      float64 x
      float64 y
      float64 z
    geometry_msgs/Quaternion orientation #旋转角度
      float64 x
      float64 y
      float64 z
      float64 w
int8[] data
结束建图服务
- 名称：/perception/post_processing
- 类型：service
- 数据类型：naviai_localization_msgs/Post_processing
int method # 结束方式
int32 METHOD_NORMAL=0    #正常结束
int32 METHOD_DROP=1    #结束并丢弃
---
bool success    # 结果
string message  # 返回消息
建图结果发布接口
- 名称：/perception/mapping_result
- 类型：topic/pub
- 数据类型：naviai_localization_msgs/MappingResult
std_msgs/Header header
nav_msgs/MapMetaData info
int8[] data
建图错误码
- 名称：/perception/mapping_code 
- 类型：topic
- 数据类型：module_common_msgs/ModuleStatus
int32 IDLE =         0 # 算法未启动 / 无任务分配
int32 INITIALIZING = 1 # 算法启动阶段
int32 RUNNING =      2 # 算法正常迭代
int32 PAUSED =       3 # 算法临时暂停
int32 COMPLETED =    4 # 单次任务结束
int32 DEGRADED =     5 # 算法非最优运行
int32 ERROR =        6 # 算法核心故障
int32 RECOVERING =   7 # 异常后尝试恢复
int32 SYNCING =      8 # 算法等待上下游数据


int32 status        # 算法运行状态
ErrorInfo[] error_info
  int32 code          # 算法错误码
  string message      # 错误码详细信息
获取可用地图列表服务
- 名称：/zj_humanoid/navigation/get_map_list
- 类型：service
- 数据类型：map_server_msgs/GetMapList

---
int32 code
string message
string[] map_name_list # 可用地图列表名称
设置地图服务
- 名称：/zj_humanoid/navigation/set_map
- 类型：service
- 数据类型：map_server_msgs/SetMap
string map_name # 需要设置的地图名称
---
int32 code
string message
获取当前地图信息
- 名称：/zj_humanoid/navigation/get_cur_map_info
- 类型：service
- 数据类型：map_server_msgs/GetCurMapInfo
---
int32 code
string message
MapInfo map_info # 地图信息
全局地图接口
- 名称：/zj_humanoid/navigation/map 
- 类型：topic
- 数据类型：nav_msgs/OccupancyGrid
std_msgs/Header header
  uint32 seq
  time stamp
  string frame_id
nav_msgs/MapMetaData info
  time map_load_time
  float32 resolution
  uint32 width
  uint32 height
  geometry_msgs/Pose origin
    geometry_msgs/Point position #地图左下角坐标
      float64 x
      float64 y
      float64 z
    geometry_msgs/Quaternion orientation #旋转角度
      float64 x
      float64 y
      float64 z
      float64 w
int8[] data
导航协议
导航协议文档
导航接口
错误码
- 名称：/zj_humanoid/navigation/navigation_code
- 类型：topic
- 数据类型：navigation/ModuleStatus
uint8 IDLE      = 0   # 空闲
uint8 RUNNING   = 1   # 任务中
uint8 PAUSED    = 2   # 暂停
uint8 COMPLETED = 3   # 任务结束
uint8 ERROR     = 4   # 故障

uint8 status          # 模块状态
ErrorInfo[] faults    # 故障信息
  int32 code    # 故障码
  string msg    # 故障描述
导航指令发布接口
- 名称：/zj_humanoid/navigation/navigation 
- 类型：action
- 数据类型：navigation/Navigation
std_msgs/Header header                  # 消息头（包含时间戳、坐标系等）
navigation/TaskType task_type          # 任务类型
  uint8 Routine = 0                     # 常规巡逻任务
  uint8 Charge  = 1                     # 充电任务
  uint8 Parking = 2                     # 泊车任务
  uint8 Carry   = 3                     # 搬运任务
  uint8 Pushing = 4                     # 推物任务
  uint8 Towing  = 5                     # 牵引任务
  uint8 value                           # 任务类型枚举值存储字段
navigation/Waypoint[] waypoints        # 路径点 (最后一个为目标点, 其余为途经点; size >= 1)
  geometry_msgs/Pose pose               # 路径点位姿
    geometry_msgs/Point position        # 位置坐标 (x/y/z 单位：米)
      float64 x
      float64 y
      float64 z
    geometry_msgs/Quaternion orientation # 姿态四元数
      float64 x
      float64 y
      float64 z
      float64 w
  float64 distance_tolerance            # 距离容差 (到达该点的允许距离偏差，单位：米)
  float64 heading_tolerance             # 航向容差 (到达该点的允许航向偏差，单位：弧度)
navigation/Translation translation     # 平移要求
  bool enable                           # 是否启用平移功能
  float64 heading                       # 平移朝向（弧度，仅enable=true时生效）

---

std_msgs/Header header                  # 消息头
duration duration                      # 任务总用时 (单位：分钟)
float64 distance_deviation             # 到达目标点的距离偏差 (单位：米)
float64 heading_deviation              # 到达目标点的航向偏差 (单位：弧度，注：原red为笔误，应为rad)
navigation/NavigationState state       # 任务完成状态
  uint8 Idle = 0                        # 空闲状态（未启动任何任务）
  uint8 Active = 1                      # 任务已激活（待执行）
  uint8 Running = 2                     # 任务执行中（导航运动中）
  uint8 Arrived = 3                     # 到达目标点（未完成最终校验）
  uint8 Canceling = 4                   # 任务取消中（接收到取消指令，正在停止）
  uint8 Cancelled = 5                   # 任务已取消（用户主动终止）
  uint8 Succeeded = 6                   # 任务成功完成（到达目标且偏差符合要求）
  uint8 Failed = 7                      # 任务失败（未到达目标，如路径规划失败）
  uint8 Error = 8                       # 系统错误（硬件/通信异常导致任务中断）
  uint8 Aborted = 9                     # 任务中止（外部干预/安全触    发停止）
  uint8 value                           # 状态枚举值存储字段
navigation/ErrorInfo[] causes          # 任务未成功的原因（仅state≠Succeeded时有效）
  int32 code                            # 故障码（自定义错误编码，0表示无错误）
  string msg                            # 故障描述（人类可读的错误信息）

---

std_msgs/Header header                  # 消息头
navigation/NavigationState state       # 导航算法当前状态
  uint8 Idle = 0                        # 空闲状态（算法未运行）
  uint8 Active = 1                      # 算法已激活（待接收路径）
  uint8 Running = 2                     # 算法运行中（实时规划/控制）
  uint8 Arrived = 3                     # 到达目标点（算法待退出）
  uint8 Canceling = 4                   # 算法取消中（正在清理资源）
  uint8 Cancelled = 5                   # 算法已取消（用户终止）
  uint8 Succeeded = 6                   # 算法执行成功（任务完成）
  uint8 Failed = 7                      # 算法执行失败（路径规划/控制失败）
  uint8 Error = 8                       # 算法内部错误（参数异常/计算错误）
  uint8 Aborted = 9                     # 算法中止（安全机制触发）
  uint8 value                           # 状态枚举值存储字段
navigation/ErrorInfo[] faults          # 实时故障信息列表（多故障场景）
  int32 code                            # 故障码
  string msg                            # 故障描述
速度指令接口
- 名称：/zj_humanoid/cmd_vel/calib 
- 类型：topic
- 数据类型：geometry_msgs::Twist
geometry_msgs/Vector3 linear   # 线速度（笛卡尔坐标系下，x/y/z 三个方向）
  float64 x  # x 轴/方向分量
  float64 y  # y 轴/方向分量
  float64 z  # z 轴/方向分量
geometry_msgs/Vector3 angular  # 角速度（绕笛卡尔坐标系 x/y/z 轴的旋转速度）
  float64 x  # x 轴/方向分量
  float64 y  # y 轴/方向分量
  float64 z  # z 轴/方向分量
感知协议
局部障碍物接口
- 名称：/zj_humanoid/navigation/local_map
- 类型：topic
- 数据类型：navigation/LocalMap
std_msgs/Header header
  uint32 seq
  time stamp
  string frame_id
nav_msgs/MapMetaData info
  time map_load_time
  float32 resolution 
  uint32 width
  uint32 height
  geometry_msgs/Pose origin
    geometry_msgs/Point position #地图左下角坐标
      float64 x
      float64 y
      float64 z
    geometry_msgs/Quaternion orientation #旋转角度
      float64 x
      float64 y
      float64 z
      float64 w
LocalMapData[] data
  bool occupancy      # 是否占用
  int8 semantic       # 语义
  bool dynamic        # 是否是动态
  float64 speed       # 移动速度 m/s
  float64 direction   # 移动方向 [-pi, pi]
感知错误码
- 名称：/zj_humanoid/perception/perception_code 
- 类型：topic
- 数据类型：module_common_msgs/ModuleStatus
int32 IDLE =         0 # 算法未启动 / 无任务分配
int32 INITIALIZING = 1 # 算法启动阶段
int32 RUNNING =      2 # 算法正常迭代
int32 PAUSED =       3 # 算法临时暂停
int32 COMPLETED =    4 # 单次任务结束
int32 DEGRADED =     5 # 算法非最优运行
int32 ERROR =        6 # 算法核心故障
int32 RECOVERING =   7 # 异常后尝试恢复
int32 SYNCING =      8 # 算法等待上下游数据


int32 status        # 算法运行状态
ErrorInfo[] error_info
  int32 code          # 算法错误码
  string message      # 错误码详细信息
感知版本信息
- 名称：/zj_humanoid/perception/perception_version 
- 类型：service
- 数据类型：std_srv/Trigger
# Request（请求）
--- 
# Response（响应）
bool success
string message
定位协议
定位错误码
- 名称：/zj_humanoid/perception/location_code 
- 类型：topic
- 数据类型：module_common_msgs/ModuleStatus
int32 IDLE =         0 # 算法未启动 / 无任务分配
int32 INITIALIZING = 1 # 算法启动阶段
int32 RUNNING =      2 # 算法正常迭代
int32 PAUSED =       3 # 算法临时暂停
int32 COMPLETED =    4 # 单次任务结束
int32 DEGRADED =     5 # 算法非最优运行
int32 ERROR =        6 # 算法核心故障
int32 RECOVERING =   7 # 异常后尝试恢复
int32 SYNCING =      8 # 算法等待上下游数据


int32 status        # 算法运行状态
ErrorInfo[] error_info
  int32 code          # 算法错误码
  string message      # 错误码详细信息
定位信息接口
- 名称：/zj_humanoid/navigation/odom_info 
- 类型：topic/sub
- 数据类型：nav_msgs/Odometry
std_msgs/Header header
  uint32 seq
  time stamp
  string frame_id
string child_frame_id
geometry_msgs/PoseWithCovariance pose
  geometry_msgs/Pose pose
    geometry_msgs/Point position #位置
      float64 x
      float64 y
      float64 z
    geometry_msgs/Quaternion orientation #姿态
      float64 x
      float64 y
      float64 z
      float64 w
  float64[36] covariance
geometry_msgs/TwistWithCovariance twist
  geometry_msgs/Twist twist
    geometry_msgs/Vector3 linear #线速度
      float64 x
      float64 y
      float64 z
    geometry_msgs/Vector3 angular #角速度
      float64 x
      float64 y
      float64 z
  float64[36] covariance
定位接口
- 名称：/zj_humanoid/perception/reloc 
- 类型：service
- 数据类型：naviai_localization_msgs/Lio
string method
string map_path
float32 x_pos
float32 y_pos
float32 z_pos
float32 x_ori
float32 y_ori
float32 z_ori
float32 w_ori

---
bool success
string message
定位版本信息
- 名称：/zj_humanoid/perception/location_version 
- 类型：service
- 数据类型：std_srv/Trigger
# Request（请求）
--- 
# Response（响应）
bool success
string message
