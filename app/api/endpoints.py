from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field
import uuid
from app.core.logging import app_logger
from app.models.memory import UserRequest, ImageData, AgentResponse, Memory
from app.models.api import APIResponse, ErrorResponse
from app.services.agent_coordinator import AgentCoordinator
from app.services.memory_service import MemoryService
from app.services.workflow import WorkflowManager


# 创建路由器
router = APIRouter()


# 会话创建请求模型
class SessionCreateRequest(BaseModel):
    user_id: Optional[str] = None


# 会话创建响应数据模型
class SessionData(BaseModel):
    session_id: str


# 聊天请求模型
class ChatRequest(BaseModel):
    session_id: str
    text: Optional[str] = None
    image: Optional[ImageData] = None
    prompt: Optional[str] = None
    budget: Optional[float] = None
    style: Optional[str] = None


# 聊天响应数据模型
class ChatResponseData(BaseModel):
    agent_type: str
    result: Dict[str, Any]
    needs_more_info: Optional[bool] = False
    missing_info: Optional[list] = None
    message: Optional[str] = None


# 依赖项：获取智能体协调器
def get_agent_coordinator() -> AgentCoordinator:
    # 这里应该从应用状态中获取协调器实例
    # 在实际应用中，这应该通过依赖注入来实现
    # 这里简化处理，假设协调器已经在其他地方初始化
    from app.main import agent_coordinator
    return agent_coordinator

# 依赖项：获取记忆服务
# def get_memory_service() -> MemoryService:
#     return MemoryService()

# 依赖项：获取工作流管理器
def get_workflow_manager() -> WorkflowManager:
    # 这里应该从应用状态中获取工作流管理器实例
    # 在实际应用中，这应该通过依赖注入来实现
    # 这里简化处理，假设工作流管理器已经在其他地方初始化
    from app.main import workflow_manager
    return workflow_manager


@router.post("/sessions", response_model=APIResponse[SessionData])
async def create_session(
    request: SessionCreateRequest,
    agent_coordinator: AgentCoordinator = Depends(get_agent_coordinator),
):
    """创建新会话"""
    app_logger.info(f"enter create_session")
    app_logger.info(f"request: {request.model_dump()}")
    
    try:
        # 生成会话ID
        session_id = str(uuid.uuid4())
        app_logger.info(f"创建新会话: {session_id}")
        
        # 创建初始记忆并存入Redis
        memory = Memory(session_id=session_id)
        if not agent_coordinator.memory_service.save_memory(memory):
            app_logger.error(f"保存会话记忆失败: {session_id}")
            raise HTTPException(status_code=500, detail="会话创建失败")
        
        # 返回会话ID
        response = APIResponse[SessionData](
            code=200,
            message="会话创建成功",
            data=SessionData(session_id=session_id)
        )
        app_logger.info(f"response: {response.model_dump()}")
        return response
    except Exception as e:
        app_logger.error(f"创建会话失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建会话失败: {e}")


@router.delete("/sessions/{session_id}", response_model=APIResponse[Dict[str, str]])
async def delete_session(
    session_id: str,
    agent_coordinator: AgentCoordinator = Depends(get_agent_coordinator)
):
    """结束会话"""
    app_logger.info(f"enter delete_session")
    app_logger.info(f"request: session_id={session_id}")
    
    try:
        # 首先检查会话是否存在
        if not agent_coordinator.memory_service.is_session_active(session_id):
            app_logger.warning(f"会话不存在: {session_id}")
            response = APIResponse[Dict[str, str]](
                code=404,
                message="会话不存在或已结束",
                data={"session_id": session_id}
            )
            app_logger.info(f"response: {response.model_dump()}")
            return response
        
        # 清除会话记忆
        result = agent_coordinator.memory_service.clear_memory(session_id)
        
        if result:
            app_logger.info(f"结束会话: {session_id}")
            response = APIResponse[Dict[str, str]](
                code=200,
                message="会话已结束",
                data={"session_id": session_id}
            )
            app_logger.info(f"response: {response.model_dump()}")
            return response
        else:
            app_logger.warning(f"结束会话失败: {session_id}")
            response = APIResponse[Dict[str, str]](
                code=500,
                message="结束会话失败",
                data={"session_id": session_id}
            )
            app_logger.info(f"response: {response.model_dump()}")
            return response
    except Exception as e:
        app_logger.error(f"结束会话失败: {e}")
        raise HTTPException(status_code=500, detail=f"结束会话失败: {e}")


@router.post("/chat", response_model=APIResponse[ChatResponseData])
async def chat(
    request: ChatRequest,
    workflow_manager: WorkflowManager = Depends(get_workflow_manager)
):
    """与智能体系统交互"""
    app_logger.info(f"enter chat")
    app_logger.info(f"request: {request.model_dump()}")
    
    try:
        # 验证请求
        if not request.text and not request.image:
            raise HTTPException(status_code=400, detail="请提供文本或图片")
        
        # 创建用户请求
        user_request = UserRequest(
            session_id=request.session_id,
            text=request.text,
            image=request.image,
            prompt=request.prompt,
            budget=request.budget,
            style=request.style
        )
        
        # 运行工作流
        response = await workflow_manager.run_workflow(user_request)
        
        # 检查是否有错误
        if "error" in response:
            raise HTTPException(status_code=500, detail=response["error"])
        
        # 构建响应数据
        chat_response_data = ChatResponseData(
            agent_type=response["agent_type"],
            result=response.get("result", {})
        )
        
        # 如果需要更多信息，添加相关字段
        if response.get("needs_more_info", False):
            chat_response_data.needs_more_info = True
            chat_response_data.missing_info = response.get("missing_info", [])
            chat_response_data.message = response.get("message", "请提供更多信息")
        
        # 返回符合RESTful规范的响应
        response = APIResponse[ChatResponseData](
            code=200,
            message="处理成功",
            data=chat_response_data
        )
        app_logger.info(f"response: {response.model_dump()}")
        return response
    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        app_logger.error(f"处理聊天请求失败: {e}")
        raise HTTPException(status_code=500, detail=f"处理聊天请求失败: {e}")


@router.get("/health", response_model=APIResponse[Dict[str, str]])
async def health_check():
    """健康检查"""
    app_logger.info(f"enter health_check")
    
    response = APIResponse[Dict[str, str]](
        code=200,
        message="服务正常",
        data={
            "status": "ok",
            "version": "1.0.0"
        }
    )
    
    app_logger.info(f"response: {response.model_dump()}")
    return response
