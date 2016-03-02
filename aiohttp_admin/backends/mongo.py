import re
from bson import ObjectId

from ..resource import AbstractResource
from ..exceptions import ObjectNotFound
from ..utils import json_response, validate_query


__all__ = ['MotorResource']


def op(filter, field, operation, value):
    if operation == 'in':
        filter[field] = {'$in': value}
    elif operation == 'like':
        filter[field] = {'$regex': '^{}'.format(re.escape(value))}
    elif operation == 'eq':
        filter[field] = {'$eq': value}
    elif operation == 'ne':
        filter[field] = {'$not': value}
    elif operation == 'le':
        filter[field] = {'$lte': value}
    elif operation == 'lt':
        filter[field] = {'$lt': value}
    elif operation == 'ge':
        filter[field] = {'$gt': value}
    elif operation == 'gt':
        filter[field] = {'$gte': value}
    else:
        raise ValueError('Operation not supported {}'.format(operation))
    return filter


def create_filter(filter):
    query = {}
    for field_name, operation in filter.items():
        if isinstance(operation, dict):
            for op_name, value in operation.items():
                query = op(query, field_name, op_name, value)
        else:
            value = operation
            query[field_name] = value
    return query


class MotorResource(AbstractResource):

    def __init__(self, collection, schema, primary_key='_id', url=None):
        super().__init__(url)
        self._collection = collection
        self._primary_key = primary_key
        self._validator = schema

    @property
    def db(self):
        return self._db

    @property
    def pk(self):
        return self._pk

    async def list(self, request):
        q = validate_query(request.GET)

        page = q['_page']
        # sort_field = q['_sortField']
        per_page = q['_perPage']
        filters = q.get('_filters')

        # TODO: add sorting support
        # sort_dir = q['_sortDir']

        offset = (page - 1) * per_page
        limit = per_page
        if filters:
            query = create_filter(filters)
        query = {}
        cursor = self._collection.find(query).skip(offset).limit(limit)
        entities = await cursor.to_list(limit)
        count = await self._collection.find(query).count()
        headers = {'X-Total-Count': str(count)}
        return json_response(entities, headers=headers)

    async def detail(self, request):
        entity_id = request.match_info['entity_id']
        query = {self._primary_key: ObjectId(entity_id)}

        doc = await self._collection.find_one(query)
        if not doc:
            msg = 'Entity with id: {} not found'.format(entity_id)
            raise ObjectNotFound(msg)

        entity = dict(doc)
        return json_response(entity)

    async def create(self, request):
        raw_payload = await request.read()
        data = validate_payload(raw_payload, self._schema)

        entity_id = await self._collection.insert(data)
        query = {self._primary_key: ObjectId(entity_id)}
        doc = await self._collection.find_one(query)

        return json_response(doc)

    async def update(self, request):
        entity_id = request.match_info['entity_id']
        raw_payload = await request.read()
        data = validate_payload(raw_payload, self._schema)
        query = {self._primary_key: ObjectId(entity_id)}

        doc = await self._collection.find_and_modify(
            query, {"$set": data}, upsert=False, new=True)

        if not doc:
            msg = 'Entity with id: {} not found'.format(entity_id)
            raise ObjectNotFound(msg)

        return json_response(doc)

    async def delete(self, request):
        entity_id = request.match_info['entity_id']
        # TODO: fix ObjectId is not always valid case
        query = {self._primary_key: ObjectId(entity_id)}
        await self._collection.remove(query)
        return json_response({'status': 'deleted'})
