import json
from typing import Optional
import redis
from app.core.config import settings
from app.core.logging import app_logger
from app.models.memory import Memory, UserRequest, AgentResponse


class MemoryService:
    """记忆服务，用于管理会话状态和历史记录"""
    
    def __init__(self):
        """初始化记忆服务"""
        try:
            # 连接Redis
            self.redis_client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD if settings.REDIS_PASSWORD else None,
                decode_responses=False  # 不自动解码，因为我们存储的是JSON字符串
            )
            app_logger.info("Redis连接成功")
        except Exception as e:
            app_logger.error(f"Redis连接失败: {e}")
            raise
    
    def get_memory(self, session_id: str) -> Memory:
        """获取会话记忆"""
        try:
            # 从Redis获取会话记忆
            memory_data = self.redis_client.get(f"memory:{session_id}")
            
            if memory_data:
                # 反序列化记忆数据
                memory_dict = json.loads(memory_data)
                memory = Memory.parse_obj(memory_dict)
                # 刷新超时时间
                self.redis_client.expire(f"memory:{session_id}", settings.SESSION_TTL)
                app_logger.debug(f"获取会话记忆成功: {session_id}")
            else:
                # 创建新的记忆对象
                memory = Memory(session_id=session_id)
                app_logger.debug(f"创建新会话记忆: {session_id}")
                
            return memory
        except Exception as e:
            app_logger.error(f"获取会话记忆失败: {e}")
            # 出错时返回新的记忆对象
            return Memory(session_id=session_id)
    
    def save_memory(self, memory: Memory) -> bool:
        """保存会话记忆"""
        try:
            # 序列化并保存记忆数据
            memory_dict = memory.dict()
            # 将datetime字段转换为字符串
            for interaction in memory_dict.get("interactions", []):
                if "timestamp" in interaction:
                    interaction["timestamp"] = interaction["timestamp"].isoformat()
            if "created_at" in memory_dict:
                memory_dict["created_at"] = memory_dict["created_at"].isoformat()
            if "updated_at" in memory_dict:
                memory_dict["updated_at"] = memory_dict["updated_at"].isoformat()
                
            memory_data = json.dumps(memory_dict)
            self.redis_client.set(
                f"memory:{memory.session_id}", 
                memory_data,
                ex=settings.SESSION_TTL
            )
            app_logger.debug(f"保存会话记忆成功: {memory.session_id}")
            return True
        except Exception as e:
            app_logger.error(f"保存会话记忆失败: {e}")
            return False
    
    def clear_memory(self, session_id: str) -> bool:
        """清除会话记忆"""
        try:
            # 清除会话记忆
            self.redis_client.delete(f"memory:{session_id}")
            app_logger.debug(f"清除会话记忆成功: {session_id}")
            return True
        except Exception as e:
            app_logger.error(f"清除会话记忆失败: {e}")
            return False
    
    def is_session_active(self, session_id: str) -> bool:
        """检查会话是否活跃（未被删除）
        
        Args:
            session_id: 会话ID
            
        Returns:
            True如果会话活跃，False如果会话已被删除
        """
        try:
            # 直接检查Redis中是否存在该会话的key
            key_exists = self.redis_client.exists(f"memory:{session_id}")
            return bool(key_exists)
        except Exception as e:
            app_logger.error(f"检查会话状态失败: {e}")
            # 出错时默认认为会话活跃
            return True
    
    def add_interaction(self, session_id: str, agent_type: str, request: UserRequest, response: AgentResponse) -> bool:
        """添加交互记录"""
        try:
            # 获取会话记忆
            memory = self.get_memory(session_id)
            
            # 添加交互记录
            memory.add_interaction(
                agent_type=agent_type,
                request=request.dict(),
                response=response.dict()
            )
            
            # 保存会话记忆
            return self.save_memory(memory)
        except Exception as e:
            app_logger.error(f"添加交互记录失败: {e}")
            return False