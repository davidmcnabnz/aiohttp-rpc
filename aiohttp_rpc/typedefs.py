import typing


if typing.TYPE_CHECKING:
    from . import protocol  # NOQA

JsonRpcIdType = typing.Union[int, str]
JSONEncoderType = typing.Callable[[typing.Any], str]
UnboundJSONEncoderType = typing.Callable[[typing.Any, typing.Any], str]
SingleRequestProcessorType = typing.Callable[['protocol.JsonRpcRequest'], typing.Awaitable['protocol.JsonRpcResponse']]
UnboundSingleRequestProcessorType = typing.Callable[
    [typing.Any, 'protocol.JsonRpcRequest'],
    typing.Awaitable['protocol.JsonRpcResponse'],
]

MethodDescriptionType = typing.Union[str, list, tuple, 'protocol.JsonRpcRequest']
MethodDescriptionsType = typing.Union[typing.Iterable[MethodDescriptionType], 'protocol.JsonRpcBatchRequest']
