import json

from unittest.mock import patch
from nose.tools import ok_, eq_, raises

from moncli import client, entities as en
from moncli.entities import column_value as cv
from moncli.enums import ColumnType, BoardKind, WebhookEventType

USERNAME = 'test.user@foobar.org' 


@patch('moncli.api_v2.get_boards')
def test_should_get_activity_logs(get_boards):

    # Arrange
    id = '12345'
    account_id = '123456'
    get_boards.return_value = [{'id': '1', 'name': 'Test Board 1'}]
    board = client.get_boards(ids=['1'])[0]
    get_boards.return_value = [{'id': '1', 'name': 'Test Board 1', 'activity_logs': [{'id': id, 'account_id': account_id}]}]

    # Act 
    activity_logs = board.get_activity_logs()

    # Assert
    ok_(activity_logs)
    eq_(activity_logs[0].id, id)
    eq_(activity_logs[0].account_id, account_id)


@patch('moncli.api_v2.get_boards')
def test_should_get_activity_logs_with_kwargs(get_boards):

    # Arrange
    id = '12345'
    item_id = '1234'
    account_id = '123456'
    get_boards.return_value = [{'id': '1', 'name': 'Test Board 1'}]
    board = client.get_boards(ids=['1'])[0]
    get_boards.return_value = [{'id': '1', 'name': 'Test Board 1', 'activity_logs': [{'id': id, 'account_id': account_id}]}]

    # Act 
    activity_logs = board.get_activity_logs(item_ids=[item_id])

    # Assert
    ok_(activity_logs)
    eq_(activity_logs[0].id, id)
    eq_(activity_logs[0].account_id, account_id)


@patch('moncli.api_v2.get_boards')
def test_should_get_board_views(get_boards):

    # Arrange
    id = '123'
    name = 'view'
    settings_str = 'settings'
    view_type = 'type'
    get_boards.return_value = [{'id': '1', 'name': 'Test Board 1'}]
    board = client.get_boards(ids=['1'])[0]
    get_boards.return_value = [{'id': '1', 'name': 'Test Board 1', 'views': [{'id': id, 'name': name, 'settings_str': settings_str, 'type': view_type}]}]

    # Act
    views = board.get_views()

    # Assert 
    ok_(views)
    eq_(views[0].id, id)
    eq_(views[0].name, name)
    eq_(views[0].settings_str, settings_str)
    eq_(views[0].type, view_type)
    

@patch('moncli.api_v2.get_boards')
@patch('moncli.api_v2.add_subscribers_to_board')
def test_should_add_subscribers(add_subscribers_to_board, get_boards):

    # Arrange
    user_id = '1'
    name = 'name'
    get_boards.return_value = [{'id': '1', 'name': 'name'}]
    add_subscribers_to_board.return_value = [{'id': user_id, 'name': name}]
    board = client.get_boards(ids=['1'])[0]

    # Act
    subscribers = board.add_subscribers([user_id])

    # Assert
    ok_(subscribers)
    eq_(subscribers[0].id, user_id)
    eq_(subscribers[0].name, name)


@patch('moncli.api_v2.get_boards')
def test_should_get_board_subscribers(get_boards):

    # Arrange
    user_id = '1'
    name = 'name'
    get_boards.return_value = [{'id': '1', 'name': 'name'}]
    board = client.get_boards(ids=['1'])[0]
    get_boards.return_value = [{'id': '1', 'subscribers': [{'id': user_id, 'name': name}]}]

    # Act
    subscribers = board.get_subscribers()

    # Assert
    ok_(subscribers)
    eq_(subscribers[0].id, user_id)
    eq_(subscribers[0].name, name)


@patch('moncli.api_v2.get_boards')
@patch('moncli.api_v2.delete_subscribers_from_board')
def test_should_delete_subscribers_from_board(delete_subscribers_from_board, get_boards):

    # Arrange
    user_id = '1'
    name = 'name'
    get_boards.return_value = [{'id': '1', 'name': 'name'}]
    board = client.get_boards(ids=['1'])[0]
    delete_subscribers_from_board.return_value = [{'id': user_id, 'name': name}]

    # Act
    subscribers = board.delete_subscribers(['1'])

    # Assert
    ok_(subscribers)
    eq_(subscribers[0].id, user_id)
    eq_(subscribers[0].name, name)


@patch('moncli.api_v2.create_board')
@patch('moncli.api_v2.create_column')
def test_should_add_new_column(create_column, create_board):

    # Arrange
    title = 'Text Column 1'
    column_type = ColumnType.text
    create_board.return_value = {'id': '1', 'name': 'Test Board 1'}
    create_column.return_value = {'id': '1', 'title': title, 'type': column_type.name}
    board = client.create_board('Test Board 1', BoardKind.public)

    # Act 
    column = board.add_column(title, column_type)

    # Assert
    ok_(column != None)
    eq_(column.title, title)
    eq_(column.column_type, column_type)


@patch('moncli.api_v2.create_board')
@patch('moncli.api_v2.get_boards')
def test_should_retrieve_list_of_columns(get_boards, create_board):

    # Arrange
    title = 'Text Column 1'
    column_type = ColumnType.text
    create_board.return_value = {'id': '1', 'name': 'Test Board 1'}
    get_boards.return_value = [{'id': '1', 'columns': [{'id': '1', 'title': title, 'type': column_type.name}]}]
    board = client.create_board('Test Board 1', BoardKind.public)

    # Act 
    columns = board.get_columns()

    # Assert
    ok_(columns != None)
    eq_(len(columns), 1)
    eq_(columns[0].title, title)
    eq_(columns[0].column_type, column_type)


@patch('moncli.api_v2.create_board')
@patch('moncli.api_v2.create_group')
def test_should_create_a_new_group(create_group, create_board):

    # Arrange
    title = 'Group 1'
    create_board.return_value = {'id': '1', 'name': 'Test Board 1'}
    create_group.return_value = {'id': '1', 'title': title}
    board = client.create_board('Test Board 1', BoardKind.public)

    # Act 
    group = board.add_group(title)

    # Assert
    ok_(group != None)
    eq_(group.title, title)


@patch('moncli.api_v2.create_board')
@patch('moncli.api_v2.get_boards')
def test_should_retrieve_a_list_of_groups(get_boards, create_board):

    # Arrange
    title = 'Group 1'
    create_board.return_value = {'id': '1', 'name': 'Test Board 1'}
    get_boards.return_value = [{'id': '1', 'groups': [{'id': '1', 'title': title}]}]
    board = client.create_board('Test Board 1', BoardKind.public)

    # Act 
    groups = board.get_groups()

    # Assert
    ok_(groups != None)
    eq_(len(groups), 1)
    eq_(groups[0].title, title)


@patch('moncli.api_v2.create_board')
@raises(en.board.NotEnoughGetGroupParameters)
def test_board_should_fail_to_retrieve_a_group_from_too_few_parameters(create_board):

    # Arrange
    create_board.return_value = {'id': '1', 'name': 'Test Board 1'}
    board = client.create_board('Test Board 1', BoardKind.public)

    # Act 
    board.get_group()


@patch('moncli.api_v2.create_board')
@raises(en.board.TooManyGetGroupParameters)
def test_board_should_fail_to_retrieve_a_group_from_too_many_parameters(create_board):

    # Arrange
    create_board.return_value = {'id': '1', 'name': 'Test Board 1'}
    board = client.create_board('Test Board 1', BoardKind.public)

    # Act 
    board.get_group(id='group1', title='Group 1')


@patch('moncli.api_v2.create_board')
@patch('moncli.api_v2.get_boards')
def test_should_retrieve_a_group_by_id(get_boards, create_board):

    # Arrange
    id = '1'
    title = 'Group 1'
    create_board.return_value = {'id': '1', 'name': 'Test Board 1'}
    get_boards.return_value = [{'id': '1', 'groups': [{'id': id, 'title': title}]}]
    board = client.create_board('Test Board 1', BoardKind.public)

    # Act 
    group = board.get_group(id=id)

    # Assert
    ok_(group != None)
    eq_(group.id, id)
    eq_(group.title, title)


@patch('moncli.api_v2.create_board')
@patch('moncli.api_v2.get_boards')
def test_should_retrieve_a_group_by_title(get_boards, create_board):

    # Arrange
    id = '1'
    title = 'Group 1'
    create_board.return_value = {'id': '1', 'name': 'Test Board 1'}
    get_boards.return_value = [{'id': '1', 'groups': [{'id': id, 'title': title}]}]
    board = client.create_board('Test Board 1', BoardKind.public)

    # Act 
    group = board.get_group(title=title)

    # Assert
    ok_(group != None)
    eq_(group.id, id)
    eq_(group.title, title)


@patch('moncli.api_v2.create_board')
@patch('moncli.api_v2.create_item')
def test_should_create_an_item(create_item, create_board):

    # Arrange
    board_id = '1'
    name = 'Item 1'
    create_board.return_value = {'id': board_id, 'name': 'Test Board 1'}
    create_item.return_value = {'id': '1', 'name': name}
    board = client.create_board('Test Board 1', BoardKind.public)

    # Act 
    item = board.add_item(name)

    # Assert
    ok_(item != None)
    eq_(item.name, name)


@patch('moncli.api_v2.create_board')
@patch('moncli.api_v2.create_item')
def test_board_should_create_an_item_within_group(create_item, create_board):

    # Arrange
    board_id = '2'
    name = 'Item 2'
    group_id = 'group2'
    create_board.return_value = {'id': board_id, 'name': 'Test Board 1'}
    create_item.return_value = {'id': '2', 'name': name}
    board = client.create_board('Test Board 1', BoardKind.public)

    # Act 
    item = board.add_item(name, group_id=group_id)

    # Assert
    ok_(item != None)
    eq_(item.name, name)



@patch('moncli.api_v2.create_board')
@patch('moncli.api_v2.create_item')
def test_board_should_create_an_item_with_dict_column_values(create_item, create_board):

    # Arrange
    board_id = '3'
    name = 'Item 3'
    group_id = 'group2'
    create_board.return_value = {'id': board_id, 'name': 'Test Board 1'}
    create_item.return_value = {'id': '3', 'name': name}
    board = client.create_board('Test Board 1', BoardKind.public)

    # Act 
    item = board.add_item(name, group_id=group_id, column_values={'status':{'index': 0}})

    # Assert
    ok_(item != None)
    eq_(item.name, name)


@patch('moncli.api_v2.create_board')
@patch('moncli.api_v2.create_item')
def test_board_should_create_an_item_with_list_column_values(create_item, create_board):

    # Arrange
    board_id = '3'
    name = 'Item 4'
    group_id = 'group2'
    create_board.return_value = {'id': board_id, 'name': 'Test Board 1'}
    create_item.return_value = {'id': '4', 'name': name}
    board = client.create_board('Test Board 1', BoardKind.public)
    status_column = cv.create_column_value(ColumnType.status, id='status', title='Status', value=json.dumps({'index': 0}), settings_str=json.dumps({'labels': {'0':'Test'}}))

    # Act 
    item = board.add_item(name, group_id=group_id, column_values=[status_column])

    # Assert
    ok_(item != None)
    eq_(item.name, name)



@patch('moncli.api_v2.create_board')
@patch('moncli.api_v2.get_boards')
def test_should_retrieve_a_list_of_items(get_boards, create_board):

    # Arrange
    board_id = '1'
    name = 'Item 1'
    create_board.return_value = {'id': board_id, 'name': 'Test Board 1'}
    get_boards.return_value = [{'id': '1', 'items': [{'id': '1', 'name': name}]}]
    board = client.create_board('Test Board 1', BoardKind.public)

    # Act 
    items = board.get_items()

    # Assert
    ok_(items != None)
    eq_(len(items), 1)
    eq_(items[0].name, name)


@patch('moncli.api_v2.create_board')
@patch('moncli.api_v2.get_items_by_column_values')
def test_should_retrieve_a_list_of_items_by_column_value(get_items_by_column_values, create_board):

    # Arrange
    board_id = '1'
    name = 'Item 1'
    create_board.return_value = {'id': board_id, 'name': 'Test Board 1'}
    get_items_by_column_values.return_value = [{'id': '1', 'name': name}]
    board = client.create_board('Test Board 1', BoardKind.public)

    # Act 
    column_value = cv.create_column_value(ColumnType.text, id='text_column_01', title='Text Column 01', text='Some Value', value=json.dumps('Some Value'))
    items = board.get_items_by_column_values(column_value)

    # Assert
    ok_(items != None)
    eq_(len(items), 1)
    eq_(items[0].name, name)


@patch('moncli.api_v2.create_board')
@raises(en.board.NotEnoughGetColumnValueParameters)
def test_should_fail_from_too_few_parameters(create_board):

    # Arrange
    create_board.return_value = {'id': '1', 'name': 'Test Board 1'}
    board = client.create_board('Test Board 1', BoardKind.public)

    # Act 
    board.get_column_value()


@patch('moncli.api_v2.create_board')
@raises(en.board.TooManyGetColumnValueParameters)
def test_should_fail_from_too_many_parameters(create_board):

    # Arrange
    create_board.return_value = {'id': '1', 'name': 'Test Board 1'}
    board = client.create_board('Test Board 1', BoardKind.public)

    # Act 
    board.get_column_value(id='text_column_01', title='Text Column 01')


@patch('moncli.api_v2.create_board')
@patch('moncli.api_v2.get_boards')
def test_should_get_column_value_by_id(get_boards, create_board):

    # Arrange
    create_board.return_value = {'id': '1', 'name': 'Test Board 1'}
    get_boards.return_value = [{'id': '1', 'columns':[{'id': 'text_column_01', 'title': 'Text Column 01', 'type': 'text'}]}]
    board = client.create_board('Test Board 1', BoardKind.public)

    # Act 
    column_value = board.get_column_value(id='text_column_01')

    # Assert
    ok_(column_value != None)
    eq_(column_value.id, 'text_column_01')
    eq_(column_value.title, 'Text Column 01')
    eq_(type(column_value), cv.TextValue)



@patch('moncli.api_v2.create_board')
@patch.object(en.Board, 'get_columns')
def test_should_get_column_value_by_title(get_columns, create_board):

    # Arrange
    create_board.return_value = {'id': '1', 'name': 'Test Board 1'}
    get_columns.return_value = [en.Column({'id': 'text_column_01', 'title': 'Text Column 01', 'type': 'text'})]
    board = client.create_board('Test Board 1', BoardKind.public)

    # Act 
    column_value = board.get_column_value(title='Text Column 01')

    # Assert
    ok_(column_value != None)
    eq_(column_value.id, 'text_column_01')
    eq_(column_value.title, 'Text Column 01')
    eq_(type(column_value), cv.TextValue)


@patch('moncli.api_v2.create_board')
@raises(en.board.WebhookConfigurationError)
def test_should_fail_to_create_webhook_from_invalid_event(create_board):

    # Arrange
    board_id = '1'
    create_board.return_value = {'id': board_id, 'name': 'Test Board 1'}
    board = client.create_board('Test Board 1', BoardKind.public)

    # Act
    board.create_webhook('http://test.webhook.com/webhook/test', WebhookEventType.create_item, columnId='test_1')



@patch('moncli.api_v2.create_board')
@patch('moncli.api_v2.create_webhook')
def test_should_create_webhook(create_webhook, create_board):

    # Arrange
    board_id = '1'
    webhook_id = '12345'
    create_board.return_value = {'id': board_id, 'name': 'Test Board 1'}
    create_webhook.return_value = {'board_id': board_id, 'id': webhook_id}
    board = client.create_board('Test Board 1', BoardKind.public)

    # Act
    webhook = board.create_webhook('http://test.webhook.com/webhook/test', WebhookEventType.create_item)

    # Assert 
    ok_(webhook != None)
    eq_(webhook.board_id, board_id)
    eq_(webhook.id, webhook_id)
    ok_(webhook.is_active)


@patch('moncli.api_v2.create_board')
@patch('moncli.api_v2.delete_webhook')
def test_should_delete_webhook(delete_webhook, create_board):

    # Arrange
    board_id = '1'
    webhook_id = '12345'
    create_board.return_value = {'id': board_id, 'name': 'Test Board 1'}
    delete_webhook.return_value = {'board_id': board_id, 'id': webhook_id}
    board = client.create_board('Test Board 1', BoardKind.public)

    # Act
    webhook = board.delete_webhook(webhook_id)

    # Assert 
    ok_(webhook != None)
    eq_(webhook.board_id, board_id)
    eq_(webhook.id, webhook_id)
    ok_(not webhook.is_active)