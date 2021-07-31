import abc
import types
import typing
from functools import partial

from .. import errors, protocol, typedefs, utils


__all__ = (
    'BaseJsonRpcClient',
)


class BaseJsonRpcClient(abc.ABC):
    error_map: typing.Dict[int, typing.Type[errors.JsonRpcError]] = {
        error.code: error
        for error in errors.DEFAULT_KNOWN_ERRORS
    }
    json_serialize: typing.Callable = utils.json_serialize

    async def __aenter__(self) -> 'BaseJsonRpcClient':
        await self.connect()
        return self

    async def __aexit__(self,
                        exc_type: typing.Optional[typing.Type[BaseException]],
                        exc_value: typing.Optional[BaseException],
                        traceback: typing.Optional[types.TracebackType]) -> None:
        await self.disconnect()

    def __getattr__(self, method_name: str) -> typing.Callable:
        return partial(self.call, method_name)

    @abc.abstractmethod
    async def connect(self) -> None:
        pass

    @abc.abstractmethod
    async def disconnect(self) -> None:
        pass

    async def call(self, method_name: str, *args, **kwargs) -> typing.Any:
        request = protocol.JsonRpcRequest(id=utils.get_random_id(), method_name=method_name, args=args, kwargs=kwargs)
        response = await self.direct_call(request)

        assert response is not None  # Because it isn't a notification

        if response.error is not None:
            raise response.error

        return response.result

    async def notify(self, method_name: str, *args, **kwargs) -> None:
        request = protocol.JsonRpcRequest(method_name=method_name, args=args, kwargs=kwargs)
        await self.direct_call(request)

    async def batch(self,
                    method_descriptions: typedefs.MethodDescriptionsType, *,
                    save_order: bool = True) -> typing.Any:
        if isinstance(method_descriptions, protocol.JsonRpcBatchRequest):
            batch_request = method_descriptions
        else:
            batch_request = protocol.JsonRpcBatchRequest(requests=[
                self._parse_method_description(method_description)
                for method_description in method_descriptions
            ])

        batch_response = await self.direct_batch(batch_request)

        assert batch_response is not None  # Because it isn't a notification

        if save_order:
            return self._collect_batch_result(batch_request, batch_response)
        else:
            return [
                response.result if response.error is None else response.error
                for response in batch_response.responses
            ]

    async def batch_notify(self, method_descriptions: typedefs.MethodDescriptionsType) -> None:
        if isinstance(method_descriptions, protocol.JsonRpcBatchRequest):
            batch_request = method_descriptions
        else:
            batch_request = protocol.JsonRpcBatchRequest(requests=[
                self._parse_method_description(method_description, is_notification=True)
                for method_description in method_descriptions
            ])

        await self.direct_batch(batch_request)

    async def direct_call(self,
                          request: protocol.JsonRpcRequest,
                          **kwargs) -> typing.Optional[protocol.JsonRpcResponse]:
        json_response, context = await self.send_json(
            request.to_dict(),
            without_response=request.is_notification,
            **kwargs,
        )

        if request.is_notification:
            return None

        response = protocol.JsonRpcResponse.from_dict(
            json_response,
            error_map=self.error_map,
            context=context,
        )

        return response

    async def direct_batch(self,
                           batch_request: protocol.JsonRpcBatchRequest,
                           **kwargs) -> typing.Optional[protocol.JsonRpcBatchResponse]:
        if not batch_request.requests:
            raise errors.InvalidRequest('You can not send an empty batch request.')

        is_notification = batch_request.is_notification

        json_response, context = await self.send_json(
            batch_request.to_list(),
            without_response=is_notification,
            **kwargs,
        )

        if is_notification:
            return None

        if not json_response:
            raise errors.ParseError('Server returned an empty batch response.')

        return protocol.JsonRpcBatchResponse.from_list(json_response)

    @abc.abstractmethod
    async def send_json(self,
                        data: typing.Any, *,
                        without_response: bool = False,
                        **kwargs) -> typing.Tuple[typing.Any, typing.Optional[dict]]:
        pass

    @staticmethod
    def _collect_batch_result(batch_request: protocol.JsonRpcBatchRequest,
                              batch_response: protocol.JsonRpcBatchResponse) -> list:
        unlinked_results = protocol.UnlinkedResults()
        responses_map: typing.Dict[typing.Any, typing.Any] = {}

        for response in batch_response.responses:
            if response.error is None:
                value = response.result
            else:
                value = response.error

            if response.id is None:
                unlinked_results.add(value)
                continue

            if response.id in responses_map:
                if isinstance(responses_map[response.id], protocol.DuplicatedResults):
                    responses_map[response.id].add(value)
                else:
                    responses_map[response.id] = protocol.DuplicatedResults(data=[
                        responses_map[response.id],
                        value,
                    ])
            else:
                responses_map[response.id] = value

        result = []

        for request in batch_request.requests:
            if request.is_notification:
                result.append(unlinked_results or None)
            else:
                result.append(responses_map.get(request.id, unlinked_results or None))

        return result

    @staticmethod
    def _parse_method_description(method_description: typedefs.MethodDescriptionType, *,
                                  is_notification: bool = False) -> protocol.JsonRpcRequest:
        if isinstance(method_description, protocol.JsonRpcRequest):
            return method_description

        request_id = None if is_notification else utils.get_random_id()

        if isinstance(method_description, str):
            return protocol.JsonRpcRequest(
                id=request_id,
                method_name=method_description,
            )

        if len(method_description) == 1:
            return protocol.JsonRpcRequest(
                id=request_id,
                method_name=method_description[0],
            )

        if len(method_description) == 2:
            return protocol.JsonRpcRequest(
                id=request_id,
                method_name=method_description[0],
                params=method_description[1],
            )

        if len(method_description) == 3:
            return protocol.JsonRpcRequest(
                id=request_id,
                method_name=method_description[0],
                args=method_description[1],
                kwargs=method_description[2],
            )

        raise errors.InvalidParams('Use string or list (length less than or equal to 3).')
