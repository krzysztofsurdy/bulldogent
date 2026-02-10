import structlog
import vertexai
from vertexai.generative_models import (
    Content,
    FunctionDeclaration,
    GenerationConfig,
    GenerativeModel,
    Part,
    Tool,
)

from bulldogent.llm.provider.config import VertexConfig
from bulldogent.llm.provider.provider import AbstractProvider
from bulldogent.llm.provider.types import (
    Message,
    MessageRole,
    ProviderResponse,
    ProviderType,
    TextResponse,
    TokenUsage,
    ToolUseResponse,
)
from bulldogent.llm.tool.types import ToolOperation, ToolOperationCall

_logger = structlog.get_logger()


def _message_to_provider_format(message: Message) -> Content:
    """
    Convert our Message to Vertex AI Content format.

    Vertex uses Content objects with role and parts (not simple dicts like OpenAI).
    """
    role = "model" if message.role == MessageRole.ASSISTANT else "user"

    return Content(
        role=role,
        parts=[Part.from_text(message.content)],
    )


def _tool_operation_to_provider_format(operation: ToolOperation) -> FunctionDeclaration:
    """
    Convert our ToolOperation to Vertex AI FunctionDeclaration.

    Vertex uses FunctionDeclaration objects (not plain dicts like OpenAI).
    """
    return FunctionDeclaration(
        name=operation.name,
        description=operation.description,
        parameters=operation.input_schema,  # Same JSON Schema format!
    )


class VertexProvider(AbstractProvider):
    """Google Cloud Vertex AI (Gemini) provider implementation."""

    config: VertexConfig

    def __init__(self, config: VertexConfig) -> None:
        super().__init__(config)
        vertexai.init(project=config.project_id, location=config.location)
        self.model = GenerativeModel(config.model)

    def identify(self) -> ProviderType:
        return ProviderType.VERTEX

    def complete(
        self,
        messages: list[Message],
        operations: list[ToolOperation] | None = None,
    ) -> ProviderResponse:
        """Send messages to Vertex AI and get response."""
        vertex_messages = [_message_to_provider_format(msg) for msg in messages]
        vertex_tools = None

        if operations:
            function_declarations = [_tool_operation_to_provider_format(op) for op in operations]
            vertex_tools = [Tool(function_declarations=function_declarations)]

        response = self.model.generate_content(
            vertex_messages,
            tools=vertex_tools,
            generation_config=GenerationConfig(
                temperature=self.config.temperature,
                max_output_tokens=self.config.max_tokens,
            ),
        )

        candidate = response.candidates[0]

        vertex_usage = response.usage_metadata
        usage = TokenUsage(
            input_tokens=vertex_usage.prompt_token_count if vertex_usage else 0,
            output_tokens=vertex_usage.candidates_token_count if vertex_usage else 0,
        )

        function_calls = []
        for part in candidate.content.parts:
            if part.function_call:
                function_calls.append(
                    ToolOperationCall(
                        id=part.function_call.name,
                        name=part.function_call.name,
                        input=dict(part.function_call.args),
                    )
                )

        if function_calls:
            _logger.info(
                "vertex_response_finished",
                reason="function_call",
                operation_calls_count=len(function_calls),
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
            )

            return ToolUseResponse(tool_operation_calls=function_calls, usage=usage)

        content = ""
        for part in candidate.content.parts:
            if part.text:
                content += part.text

        _logger.info(
            "vertex_response_finished",
            reason=str(candidate.finish_reason),
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
        )
        return TextResponse(content=content, usage=usage)
