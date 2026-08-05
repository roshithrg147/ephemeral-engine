import enum

class InteractionMode(enum.Enum):
    CHAT = "CHAT"
    ASSIST = "ASSIST"
    PROJECT = "PROJECT"
    ARCHITECT = "ARCHITECT"

class Intent(enum.Enum):
    GENERAL_CHAT = "GENERAL_CHAT"
    QUESTION_ANSWERING = "QUESTION_ANSWERING"
    WRITING = "WRITING"
    CODING = "CODING"
    DEBUGGING = "DEBUGGING"
    PROJECT_CONTINUATION = "PROJECT_CONTINUATION"
    ARCHITECTURE = "ARCHITECTURE"
    REFACTORING = "REFACTORING"
    RESEARCH = "RESEARCH"

class IntentClassifier:
    @staticmethod
    def classify(prompt: str) -> tuple[Intent, float]:
        if not prompt or not prompt.strip():
            return Intent.GENERAL_CHAT, 1.0

        p = prompt.lower()
        
        # Structural/Architectural
        if any(w in p for w in ["architecture", "design", "overview", "system flow", "structure"]):
            return Intent.ARCHITECTURE, 0.9
        
        if any(w in p for w in ["refactor", "rename", "restructure", "clean up", "extract"]):
            return Intent.REFACTORING, 0.9
            
        # Project workflow continuation
        if any(w in p for w in ["continue", "resume", "next step", "let's go on"]):
            return Intent.PROJECT_CONTINUATION, 0.8
            
        # Assisting and coding
        if any(w in p for w in ["bug", "error", "fix", "issue", "crash"]):
            return Intent.DEBUGGING, 0.9
            
        if any(w in p for w in ["write", "code", "implement", "create function", "create class"]):
            return Intent.CODING, 0.8
            
        if any(w in p for w in ["research", "investigate", "look into", "explore"]):
            return Intent.RESEARCH, 0.8
            
        # General assistance
        if any(w in p for w in ["how to", "what is", "why does", "explain", "can you"]):
            return Intent.QUESTION_ANSWERING, 0.9
            
        if any(w in p for w in ["draft", "compose", "write email", "summarize"]):
            return Intent.WRITING, 0.8
            
        # Default
        return Intent.GENERAL_CHAT, 1.0

class ModeRouter:
    @staticmethod
    def route(
        intent: Intent, 
        confidence: float, 
        active_project: bool = False, 
        explicit_instruction: str = None
    ) -> tuple[InteractionMode, str]:
        
        # 1. Explicit instructions (highest priority)
        if explicit_instruction:
            try:
                mode = InteractionMode[explicit_instruction.upper()]
                return mode, f"Explicit instruction overridden to {mode.name}"
            except KeyError:
                pass
                
        # 2. General modes (no active project context)
        if not active_project:
            if intent in [Intent.GENERAL_CHAT, Intent.QUESTION_ANSWERING, Intent.WRITING]:
                return InteractionMode.CHAT, "Default to general chat for low-context intent"
            
            if intent in [Intent.CODING, Intent.DEBUGGING, Intent.RESEARCH]:
                return InteractionMode.ASSIST, "Promoted to assist mode for coding intent without active project"
                
            # Even if intent is architecture, we don't architecture lock without active project or high confidence
            return InteractionMode.ASSIST, "Assumed assist mode for technical intent without project context"
            
        # 3. Project modes (active project context exists)
        else:
            if intent in [Intent.ARCHITECTURE, Intent.REFACTORING]:
                if confidence > 0.8:
                    return InteractionMode.ARCHITECT, "Promoted to Architect mode based on structural intent"
                else:
                    return InteractionMode.PROJECT, "Insufficient confidence for Architect mode, falling back to Project"
            
            # Demotion rule
            if intent in [Intent.GENERAL_CHAT, Intent.WRITING]:
                return InteractionMode.CHAT, "Demoted to Chat mode due to unrelated conversation"
                
            return InteractionMode.PROJECT, "Active project mode maintained"


class MemorySelector:
    @staticmethod
    def get_layer_config(mode: InteractionMode) -> dict:
        if mode == InteractionMode.CHAT:
            return {
                "use_project_memory": False,
                "use_architecture": False,
                "retrieval_depth": "minimal",
                "max_history_turns": 3
            }
        elif mode == InteractionMode.ASSIST:
            return {
                "use_project_memory": False,
                "use_architecture": False,
                "retrieval_depth": "lightweight",
                "max_history_turns": 6
            }
        elif mode == InteractionMode.PROJECT:
            return {
                "use_project_memory": True,
                "use_architecture": True,  # blueprint loading
                "retrieval_depth": "fusion",
                "max_history_turns": 10
            }
        elif mode == InteractionMode.ARCHITECT:
            return {
                "use_project_memory": True,
                "use_architecture": True,
                "retrieval_depth": "full",
                "enforce_policy": True,
                "architecture_lock": True,
                "max_history_turns": 15
            }
        return {}
