from typing import Dict, Any, TypedDict, Optional, List
from langgraph.graph import StateGraph
from app.core.logging import app_logger
from app.models.memory import UserRequest
from app.services.intent_service import IntentRecognizer
from app.services.scoring_agent import ScoringAgent
from app.services.recommendation_agent import RecommendationAgent
from app.services.default_agent import DefaultAgent
from app.services.memory_service import MemoryService


# 定义状态类型
class AgentState(TypedDict):
    session_id: str
    request: Dict[str, Any]
    memory: Optional[Dict[str, Any]]
    intent: Optional[str]
    response: Optional[Dict[str, Any]]
    error: Optional[str]
    needs_more_info: Optional[bool]  # 是否需要更多信息
    missing_info: Optional[List[str]]  # 缺失的信息类型


class WorkflowManager:
    """工作流管理器，用于构建和管理LangGraph工作流"""
    
    def __init__(
        self,
        intent_recognizer: IntentRecognizer,
        scoring_agent: ScoringAgent,
        recommendation_agent: RecommendationAgent,
        default_agent: DefaultAgent,
        memory_service: MemoryService
    ):
        """初始化工作流管理器
        
        Args:
            intent_recognizer: 意图识别服务
            scoring_agent: 试衣评分Agent
            recommendation_agent: 单品推荐Agent
            default_agent: 默认Agent
            memory_service: 记忆服务
        """
        self.intent_recognizer = intent_recognizer
        self.scoring_agent = scoring_agent
        self.recommendation_agent = recommendation_agent
        self.default_agent = default_agent
        self.memory_service = memory_service
        
        # 创建工作流
        self.workflow = self._create_workflow()
    
    def _create_workflow(self) -> StateGraph:
        """创建工作流
        
        Returns:
            工作流图
        """
        # 创建工作流图
        workflow = StateGraph(AgentState)
        
        # 添加节点
        workflow.add_node("intent_recognition", self._recognize_intent)
        workflow.add_node("check_recommendation_info", self._check_recommendation_info)
        workflow.add_node("ask_for_info", self._ask_for_info)
        workflow.add_node("scoring", self._process_scoring)
        workflow.add_node("recommendation", self._process_recommendation)
        workflow.add_node("default", self._process_default)
        
        # 定义边和条件
        workflow.add_conditional_edges(
            "intent_recognition",
            lambda state: state["intent"],
            {
                "scoring": "scoring",
                "recommendation": "check_recommendation_info",
                "default": "default"
            }
        )
        
        # 推荐信息检查节点的边
        workflow.add_conditional_edges(
            "check_recommendation_info",
            lambda state: state.get("needs_more_info", False),
            {
                True: "ask_for_info",
                False: "recommendation"
            }
        )
        
        # 询问信息节点的边 - 直接连接到推荐节点
        workflow.add_edge("ask_for_info", "recommendation")
        
        # 设置入口节点
        workflow.set_entry_point("intent_recognition")
        
        # 编译工作流
        return workflow.compile()
    
    async def _recognize_intent(self, state: AgentState) -> AgentState:
        """识别意图
        
        Args:
            state: 当前状态
            
        Returns:
            更新后的状态
        """
        try:
            # 从状态中获取请求和会话ID
            request_dict = state["request"]
            session_id = state["session_id"]
            
            # 创建UserRequest对象
            request = UserRequest.parse_obj(request_dict)
            
            # 获取会话记忆
            memory = self.memory_service.get_memory(session_id)
            
            # 识别意图
            intent = await self.intent_recognizer.recognize(request, memory)
            app_logger.info(f"识别到的意图: {intent}")
            
            # 更新状态
            state["intent"] = intent
            # 将更新后的请求保存回状态中（包含从文本中提取的预算和风格信息）
            state["request"] = request.dict()
            
            # 初始化其他状态字段
            state["needs_more_info"] = False
            state["missing_info"] = []
            
            return state
            
        except Exception as e:
            app_logger.error(f"识别意图失败: {e}")
            # 出错时设置默认意图
            state["intent"] = "default"
            state["error"] = f"识别意图失败: {e}"
            
            return state
            
    async def _check_recommendation_info(self, state: AgentState) -> AgentState:
        """检查推荐所需信息是否完整
        
        Args:
            state: 当前状态
            
        Returns:
            更新后的状态
        """
        try:
            # 从状态中获取请求
            request_dict = state["request"]
            request = UserRequest.parse_obj(request_dict)
            
            # 检查是否缺少预算和风格信息
            missing_info = []
            
            # 检查预算信息
            if not request.budget:
                missing_info.append("budget")
                
            # 检查风格信息 - 只支持两种风格：运动(sports)和休闲(casual)
            if not request.style or request.style not in ["sports", "casual"]:
                missing_info.append("style")
                
            # 如果缺少信息，设置需要更多信息标志
            if missing_info:
                state["needs_more_info"] = True
                state["missing_info"] = missing_info
                app_logger.info(f"推荐需要更多信息: {missing_info}")
            else:
                state["needs_more_info"] = False
                
            return state
            
        except Exception as e:
            app_logger.error(f"检查推荐信息失败: {e}")
            # 出错时继续处理推荐
            state["needs_more_info"] = False
            state["error"] = f"检查推荐信息失败: {e}"
            
            return state
            
    async def _ask_for_info(self, state: AgentState) -> AgentState:
        """询问缺失的信息
        
        Args:
            state: 当前状态
            
        Returns:
            更新后的状态
        """
        try:
            # 从状态中获取请求和会话ID
            request_dict = state["request"]
            session_id = state["session_id"]
            missing_info = state.get("missing_info", [])
            
            # 创建UserRequest对象
            request = UserRequest.parse_obj(request_dict)
            
            # 构建询问信息的响应
            response = {
                "agent_type": "recommendation",
                "needs_more_info": True,
                "missing_info": missing_info,
                "message": "为了给您提供更准确的搭配推荐，请提供以下信息："
            }
            
            # 根据缺失的信息类型添加具体询问
            if "budget" in missing_info:
                response["message"] += "\n- 您的预算是多少？"
                
            if "style" in missing_info:
                response["message"] += "\n- 您偏好哪种风格？(运动/休闲)"
                response["style_options"] = ["sports", "casual"]
                
            # 更新状态
            state["response"] = response
            
            # 更新记忆
            self.memory_service.add_interaction(session_id, "recommendation_inquiry", request, response)
            
            return state
            
        except Exception as e:
            app_logger.error(f"询问信息失败: {e}")
            # 出错时设置错误信息
            state["error"] = f"询问信息失败: {e}"
            state["response"] = {
                "agent_type": "recommendation",
                "error": f"处理请求失败: {e}"
            }
            
            return state
    
    async def _process_scoring(self, state: AgentState) -> AgentState:
        """处理试衣评分请求
        
        Args:
            state: 当前状态
            
        Returns:
            更新后的状态
        """
        try:
            # 从状态中获取请求和会话ID
            request_dict = state["request"]
            session_id = state["session_id"]
            
            # 创建UserRequest对象
            request = UserRequest.parse_obj(request_dict)
            
            # 获取会话记忆
            memory = self.memory_service.get_memory(session_id)
            
            # 处理请求
            response = await self.scoring_agent.process(request, memory)
            
            # 更新状态
            state["response"] = response
            
            # 更新记忆
            if "error" not in response:
                self.memory_service.add_interaction(session_id, "scoring", request, response)
            
            return state
            
        except Exception as e:
            app_logger.error(f"处理试衣评分请求失败: {e}")
            # 出错时设置错误信息
            state["error"] = f"处理试衣评分请求失败: {e}"
            state["response"] = {
                "agent_type": "scoring",
                "error": f"处理请求失败: {e}"
            }
            
            return state
    
    async def _process_recommendation(self, state: AgentState) -> AgentState:
        """处理单品推荐请求
        
        Args:
            state: 当前状态
            
        Returns:
            更新后的状态
        """
        try:
            # 如果已经有响应（来自ask_for_info节点），则直接返回
            if state.get("response") and state["response"].get("needs_more_info", False):
                return state
                
            # 从状态中获取请求和会话ID
            request_dict = state["request"]
            session_id = state["session_id"]
            
            # 创建UserRequest对象
            request = UserRequest.parse_obj(request_dict)
            
            # 获取会话记忆
            memory = self.memory_service.get_memory(session_id)
            
            # 处理请求
            response = await self.recommendation_agent.process(request, memory)
            
            # 更新状态
            state["response"] = response
            
            # 更新记忆
            if "error" not in response:
                self.memory_service.add_interaction(session_id, "recommendation", request, response)
            
            return state
            
        except Exception as e:
            app_logger.error(f"处理单品推荐请求失败: {e}")
            # 出错时设置错误信息
            state["error"] = f"处理单品推荐请求失败: {e}"
            state["response"] = {
                "agent_type": "recommendation",
                "error": f"处理请求失败: {e}"
            }
            
            return state
    
    async def _process_default(self, state: AgentState) -> AgentState:
        """处理默认请求
        
        Args:
            state: 当前状态
            
        Returns:
            更新后的状态
        """
        try:
            # 从状态中获取请求和会话ID
            request_dict = state["request"]
            session_id = state["session_id"]
            
            # 创建UserRequest对象
            request = UserRequest.parse_obj(request_dict)
            
            # 获取会话记忆
            memory = self.memory_service.get_memory(session_id)
            
            # 处理请求
            response = await self.default_agent.process(request, memory)
            
            # 更新状态
            state["response"] = response
            
            # 更新记忆
            if "error" not in response:
                self.memory_service.add_interaction(session_id, "default", request, response)
            
            return state
            
        except Exception as e:
            app_logger.error(f"处理默认请求失败: {e}")
            # 出错时设置错误信息
            state["error"] = f"处理默认请求失败: {e}"
            state["response"] = {
                "agent_type": "default",
                "error": f"处理请求失败: {e}"
            }
            
            return state
    
    async def run_workflow(self, request: UserRequest) -> Dict[str, Any]:
        """运行工作流
        
        Args:
            request: 用户请求
            
        Returns:
            处理结果
        """
        try:
            # 创建初始状态
            initial_state: AgentState = {
                "session_id": request.session_id,
                "request": request.dict(),
                "memory": None,
                "intent": None,
                "response": None,
                "error": None,
                "needs_more_info": False,
                "missing_info": []
            }
            
            # 运行工作流
            app_logger.info(f"开始运行工作流，会话ID: {request.session_id}")
            # 根据 langgraph 0.0.19 版本，使用 invoke 方法替代 arun
            final_state = await self.workflow.ainvoke(initial_state)
            
            # 检查是否有错误
            if final_state.get("error"):
                app_logger.error(f"工作流执行出错: {final_state['error']}")
                return {
                    "error": final_state["error"],
                    "agent_type": "default"
                }
            
            # 返回处理结果
            return final_state["response"]
            
        except Exception as e:
            app_logger.error(f"运行工作流失败: {e}")
            return {
                "error": f"运行工作流失败: {e}",
                "agent_type": "default"
            }
