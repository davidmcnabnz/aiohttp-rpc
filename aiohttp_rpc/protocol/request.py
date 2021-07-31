import typing
from dataclasses import dataclass, field

from .. import constants, errors, typedefs, utils


__all__ = (
    'JsonRpcRequest',
    'JsonRpcBatchRequest',
)


@dataclass
class JsonRpcRequest:
    method_name: str
    id: typing.Optional[typedefs.JsonRpcIdType] = None
    jsonrpc: str = constants.VERSION_2_0
    extra_args: dict = field(default_factory=dict)
    context: dict = field(default_factory=dict)
    params: typing.Any = constants.NOTHING  # Use `NOTHING`, because `None` is a valid value.
    # We don't convert `args`. So `args` can be `list`, `tuple` or other type.
    args: typing.Optional[typing.Sequence] = None
    # We don't convert `kwargs`. So `kwargs` can be `dict` or other type.
    kwargs: typing.Optional[typing.Mapping] = None

    def __post_init__(self) -> None:
        utils.validate_jsonrpc(self.jsonrpc)

        if self.params is constants.NOTHING:
            self.set_args_and_kwargs(self.args, self.kwargs)
        elif self.args is None and self.kwargs is None:
            self.set_params(self.params)
        else:
            raise errors.InvalidParams('Need use params or args with kwargs.')

    def set_params(self, params: typing.Any) -> None:
        self.params = params
        self.args, self.kwargs = utils.convert_params_to_args_and_kwargs(params)

    def set_args_and_kwargs(self,
                            args: typing.Optional[typing.Sequence] = None,
                            kwargs: typing.Optional[typing.Mapping] = None) -> None:
        self.params, self.args, self.kwargs = utils.parse_args_and_kwargs(args, kwargs)

    @property
    def is_notification(self) -> bool:
        return self.id is None

    @classmethod
    def from_dict(cls, data: typing.Mapping[str, typing.Any], **kwargs) -> 'JsonRpcRequest':
        cls._validate_json_request(data)

        return cls(
            id=data.get('id'),
            method_name=data['method'],
            params=data.get('params', constants.NOTHING),
            jsonrpc=data['jsonrpc'],
            **kwargs,
        )

    def to_dict(self) -> typing.Dict[str, typing.Any]:
        data: typing.Dict[str, typing.Any] = {
            'method': self.method_name,
            'jsonrpc': self.jsonrpc,
        }

        if not self.is_notification:
            data['id'] = self.id

        if self.params is not constants.NOTHING:
            data['params'] = self.params

        return data

    @staticmethod
    def _validate_json_request(data: typing.Any) -> None:
        if not isinstance(data, typing.Mapping):
            raise errors.InvalidRequest('A request must be of the dict type.')

        if not ({'method', 'jsonrpc'}) <= data.keys():
            raise errors.InvalidRequest('A request must contain "method" and "jsonrpc".')

        utils.validate_jsonrpc(data['jsonrpc'])


@dataclass
class JsonRpcBatchRequest:
    requests: typing.Sequence[JsonRpcRequest] = field(default_factory=list)

    @property
    def is_notification(self) -> bool:
        return all(request.is_notification for request in self.requests)

    def to_list(self) -> typing.List[dict]:
        return [request.to_dict() for request in self.requests]

    @classmethod
    def from_list(cls, data: list, **kwargs) -> 'JsonRpcBatchRequest':
        return cls(requests=[
            JsonRpcRequest.from_dict(item, **kwargs)
            for item in data
        ])
