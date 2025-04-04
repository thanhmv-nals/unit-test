import pytest
import csv
import time
import os
from unittest.mock import MagicMock, patch, mock_open
from exam import OrderProcessingService, Order, APIResponse, DatabaseService, APIClient, APIException, DatabaseException, OrderStatus, OrderPriority, APIStatus


@pytest.fixture
def db_service():
    return MagicMock(spec=DatabaseService)


@pytest.fixture
def api_client():
    return MagicMock(spec=APIClient)


@pytest.fixture
def service(db_service, api_client):
    return OrderProcessingService(db_service, api_client)


@pytest.fixture(autouse=True)
def cleanup_csv_files():
    """Cleanup CSV files after each test"""
    yield
    # Find and delete all CSV files created during tests
    for file in os.listdir('.'):
        if file.startswith('orders_type_A_') and file.endswith('.csv'):
            try:
                os.remove(file)
            except OSError:
                pass  # Ignore errors if file doesn't exist or can't be deleted


# Main Process Flow Tests

def test_should_return_true_when_all_orders_processed_successfully(service, db_service):
    # Arrange
    user_id = 123
    orders = [
        Order(1, 'A', 100.0, False),
        Order(2, 'B', 150.0, True),
        Order(3, 'C', 250.0, False)
    ]
    db_service.get_orders_by_user.return_value = orders
    
    # Act
    result = service.process_orders(user_id)
    
    # Assert
    assert result is True
    db_service.get_orders_by_user.assert_called_once_with(user_id)
    assert db_service.update_order_status.call_count == 3


def test_should_return_false_when_no_orders_found(service, db_service):
    # Arrange
    user_id = 123
    db_service.get_orders_by_user.return_value = []
    
    # Act
    result = service.process_orders(user_id)
    
    # Assert
    assert result is False
    db_service.get_orders_by_user.assert_called_once_with(user_id)
    db_service.update_order_status.assert_not_called()


def test_should_return_false_when_io_error_occurs_in_process_single_order(service, db_service):
    # Arrange
    user_id = 123
    orders = [Order(1, 'A', 100.0, False)]
    db_service.get_orders_by_user.return_value = orders
    
    # Act
    with patch.object(service, '_process_single_order', side_effect=IOError("Test IO error")):
        result = service.process_orders(user_id)
    
    # Assert
    assert result is False
    db_service.get_orders_by_user.assert_called_once_with(user_id)


def test_should_return_false_when_api_exception_occurs_in_process_single_order(service, db_service):
    # Arrange
    user_id = 123
    orders = [Order(1, 'A', 100.0, False)]
    db_service.get_orders_by_user.return_value = orders
    
    # Act
    with patch.object(service, '_process_single_order', side_effect=APIException("Test API exception")):
        result = service.process_orders(user_id)
    
    # Assert
    assert result is False
    db_service.get_orders_by_user.assert_called_once_with(user_id)


def test_should_return_false_when_database_exception_occurs_in_process_single_order(service, db_service):
    # Arrange
    user_id = 123
    orders = [Order(1, 'A', 100.0, False)]
    db_service.get_orders_by_user.return_value = orders
    
    # Act
    with patch.object(service, '_process_single_order', side_effect=DatabaseException("Test DB exception")):
        result = service.process_orders(user_id)
    
    # Assert
    assert result is False
    db_service.get_orders_by_user.assert_called_once_with(user_id)


# CSV File Creation Tests

def test_should_create_csv_file_with_correct_header(service):
    # Arrange
    user_id = 123
    mock_file = mock_open()
    
    # Act
    with patch('builtins.open', mock_file):
        with patch('time.time', return_value=1234567890):
            csv_file = service._create_csv_file(user_id)
    
    # Assert
    assert csv_file == 'orders_type_A_123_1234567890.csv'
    mock_file.assert_called_once_with('orders_type_A_123_1234567890.csv', 'w', newline='')
    handle = mock_file()
    handle.write.assert_called_once()


# Single Order Processing Tests

def test_should_process_single_order_correctly(service):
    # Arrange
    order = Order(1, 'A', 100.0, False)
    csv_file = 'test.csv'
    
    # Act
    with patch.object(service, '_process_order_by_type') as mock_process_type:
        with patch.object(service, '_update_order_priority') as mock_update_priority:
            with patch.object(service, '_save_order_status') as mock_save_status:
                service._process_single_order(order, csv_file)
    
    # Assert
    mock_process_type.assert_called_once_with(order, csv_file)
    mock_update_priority.assert_called_once_with(order)
    mock_save_status.assert_called_once_with(order)


def test_should_handle_io_error_from_process_order_by_type(service):
    # Arrange
    order = Order(1, 'A', 100.0, False)
    csv_file = 'test.csv'
    
    # Act
    with patch.object(service, '_process_order_by_type', side_effect=IOError("Test IO error")):
        with pytest.raises(IOError):
            service._process_single_order(order, csv_file)
    
    # Assert
    # Verify that the exception is propagated


def test_should_handle_api_exception_from_process_order_by_type(service):
    # Arrange
    order = Order(1, 'A', 100.0, False)
    csv_file = 'test.csv'
    
    # Act
    with patch.object(service, '_process_order_by_type', side_effect=APIException("Test API exception")):
        with pytest.raises(APIException):
            service._process_single_order(order, csv_file)
    
    # Assert
    # Verify that the exception is propagated


def test_should_handle_database_exception_from_save_order_status(service):
    # Arrange
    order = Order(1, 'A', 100.0, False)
    csv_file = 'test.csv'
    
    # Act
    with patch.object(service, '_process_order_by_type'):
        with patch.object(service, '_update_order_priority'):
            with patch.object(service, '_save_order_status', side_effect=DatabaseException("Test DB exception")):
                with pytest.raises(DatabaseException):
                    service._process_single_order(order, csv_file)
    
    # Assert
    # Verify that the exception is propagated


# Order Type Processing Tests

def test_should_process_type_a_order_when_order_type_is_a(service):
    # Arrange
    order = Order(1, 'A', 100.0, False)
    csv_file = 'test.csv'
    
    # Act
    with patch.object(service, '_process_type_a_order') as mock_process_a:
        service._process_order_by_type(order, csv_file)
    
    # Assert
    mock_process_a.assert_called_once_with(order, csv_file)


def test_should_process_type_b_order_when_order_type_is_b(service):
    # Arrange
    order = Order(1, 'B', 100.0, False)
    csv_file = 'test.csv'
    
    # Act
    with patch.object(service, '_process_type_b_order') as mock_process_b:
        service._process_order_by_type(order, csv_file)
    
    # Assert
    mock_process_b.assert_called_once_with(order)


def test_should_process_type_c_order_when_order_type_is_c(service):
    # Arrange
    order = Order(1, 'C', 100.0, False)
    csv_file = 'test.csv'
    
    # Act
    with patch.object(service, '_process_type_c_order') as mock_process_c:
        service._process_order_by_type(order, csv_file)
    
    # Assert
    mock_process_c.assert_called_once_with(order)


def test_should_set_status_to_unknown_type_when_order_type_is_invalid(service):
    # Arrange
    order = Order(1, 'D', 100.0, False)
    csv_file = 'test.csv'
    
    # Act
    service._process_order_by_type(order, csv_file)
    
    # Assert
    assert order.status == OrderStatus.UNKNOWN_TYPE


# Type A Order Processing Tests

def test_should_set_status_to_exported_when_type_a_order_processed_successfully(service):
    # Arrange
    order = Order(1, 'A', 100.0, False)
    csv_file = 'test.csv'
    
    # Act
    with patch('builtins.open', mock_open()):
        service._process_type_a_order(order, csv_file)
    
    # Assert
    assert order.status == OrderStatus.EXPORTED


def test_should_add_high_value_note_when_type_a_order_amount_exceeds_150(service):
    # Arrange
    order = Order(1, 'A', 200.0, False)
    csv_file = 'test.csv'
    mock_file = mock_open()
    
    # Act
    with patch('builtins.open', mock_file):
        service._process_type_a_order(order, csv_file)
    
    # Assert
    handle = mock_file()
    assert handle.write.call_count >= 2  # Header + data + high value note


def test_should_set_status_to_export_failed_when_io_error_occurs(service):
    # Arrange
    order = Order(1, 'A', 100.0, False)
    csv_file = 'test.csv'
    
    # Act
    with patch('builtins.open', side_effect=IOError("Test IO error")):
        service._process_type_a_order(order, csv_file)
    
    # Assert
    assert order.status == OrderStatus.EXPORT_FAILED


# Type B Order Processing Tests

def test_should_set_status_to_processed_when_api_data_ge_50_and_amount_lt_100(service, api_client):
    # Arrange
    order = Order(1, 'B', 80.0, False)
    api_client.call_api.return_value = APIResponse(APIStatus.SUCCESS, 60)
    
    # Act
    service._process_type_b_order(order)
    
    # Assert
    assert order.status == OrderStatus.PROCESSED
    api_client.call_api.assert_called_once_with(1)


def test_should_set_status_to_pending_when_api_data_lt_50(service, api_client):
    # Arrange
    order = Order(1, 'B', 80.0, False)
    api_client.call_api.return_value = APIResponse(APIStatus.SUCCESS, 40)
    
    # Act
    service._process_type_b_order(order)
    
    # Assert
    assert order.status == OrderStatus.PENDING
    api_client.call_api.assert_called_once_with(1)


def test_should_set_status_to_pending_when_flag_is_true(service, api_client):
    # Arrange
    order = Order(1, 'B', 180.0, True)
    api_client.call_api.return_value = APIResponse(APIStatus.SUCCESS, 160)
    
    # Act
    service._process_type_b_order(order)
    
    # Assert
    assert order.status == OrderStatus.PENDING
    api_client.call_api.assert_called_once_with(1)


def test_should_set_status_to_error_when_api_data_gt_50_and_amount_gt_100_and_flag_is_false(service, api_client):
    # Arrange
    order = Order(1, 'B', 180.0, False)
    api_client.call_api.return_value = APIResponse(APIStatus.SUCCESS, 60)
    
    # Act
    service._process_type_b_order(order)
    
    # Assert
    assert order.status == OrderStatus.ERROR
    api_client.call_api.assert_called_once_with(1)


def test_should_set_status_to_api_error_when_api_status_is_not_success(service, api_client):
    # Arrange
    order = Order(1, 'B', 80.0, False)
    api_client.call_api.return_value = APIResponse(APIStatus.ERROR, 60)
    
    # Act
    service._process_type_b_order(order)
    
    # Assert
    assert order.status == OrderStatus.API_ERROR
    api_client.call_api.assert_called_once_with(1)


def test_should_set_status_to_api_failure_when_api_exception_occurs(service, api_client):
    # Arrange
    order = Order(1, 'B', 80.0, False)
    api_client.call_api.side_effect = APIException("Test API exception")
    
    # Act
    service._process_type_b_order(order)
    
    # Assert
    assert order.status == OrderStatus.API_FAILURE
    api_client.call_api.assert_called_once_with(1)


# Type C Order Processing Tests

def test_should_set_status_to_completed_when_flag_is_true(service):
    # Arrange
    order = Order(1, 'C', 100.0, True)
    
    # Act
    service._process_type_c_order(order)
    
    # Assert
    assert order.status == OrderStatus.COMPLETED


def test_should_set_status_to_in_progress_when_flag_is_false(service):
    # Arrange
    order = Order(1, 'C', 100.0, False)
    
    # Act
    service._process_type_c_order(order)
    
    # Assert
    assert order.status == OrderStatus.IN_PROGRESS


# Priority Update Tests

def test_should_set_priority_to_high_when_amount_gt_200(service):
    # Arrange
    order = Order(1, 'A', 250.0, False)
    
    # Act
    service._update_order_priority(order)
    
    # Assert
    assert order.priority == OrderPriority.HIGH


def test_should_set_priority_to_low_when_amount_le_200(service):
    # Arrange
    order = Order(1, 'A', 200.0, False)
    
    # Act
    service._update_order_priority(order)
    
    # Assert
    assert order.priority == OrderPriority.LOW


# Status Save Tests

def test_should_save_order_status_successfully(service, db_service):
    # Arrange
    order = Order(1, 'A', 100.0, False)
    order.status = OrderStatus.EXPORTED
    order.priority = OrderPriority.HIGH
    
    # Act
    service._save_order_status(order)
    
    # Assert
    db_service.update_order_status.assert_called_once_with(1, OrderStatus.EXPORTED, OrderPriority.HIGH)


def test_should_set_status_to_db_error_when_database_exception_occurs(service, db_service):
    # Arrange
    order = Order(1, 'A', 100.0, False)
    order.status = OrderStatus.EXPORTED
    order.priority = OrderPriority.HIGH
    db_service.update_order_status.side_effect = DatabaseException("Test DB exception")
    
    # Act
    service._save_order_status(order)
    
    # Assert
    assert order.status == OrderStatus.DB_ERROR
    db_service.update_order_status.assert_called_once_with(1, OrderStatus.EXPORTED, OrderPriority.HIGH)

def test_should_set_status_to_error_when_order_status_is_error(service, db_service):
    # Arrange
    order = Order(1, 'B', 80.0, False)
    order.status = OrderStatus.ERROR
    
    # Act
    service._save_order_status(order)
    
    # Assert
    db_service.update_order_status.assert_called_once_with(1, OrderStatus.ERROR, OrderPriority.LOW)


# Integration Tests

def test_should_process_all_order_types_correctly_in_full_flow(service, db_service, api_client):
    # Arrange
    user_id = 123
    orders = [
        Order(1, 'A', 100.0, False),
        Order(2, 'B', 150.0, True),
        Order(3, 'C', 250.0, False)
    ]
    db_service.get_orders_by_user.return_value = orders
    api_client.call_api.return_value = APIResponse(APIStatus.SUCCESS, 60)
    
    # Act
    with patch('builtins.open', mock_open()):
        result = service.process_orders(user_id)
    
    # Assert
    assert result is True
    db_service.get_orders_by_user.assert_called_once_with(user_id)
    assert db_service.update_order_status.call_count == 3
    api_client.call_api.assert_called_once_with(2)
    assert orders[0].status == OrderStatus.EXPORTED
    assert orders[1].status == OrderStatus.PENDING
    assert orders[2].status == OrderStatus.IN_PROGRESS
    assert orders[0].priority == OrderPriority.LOW
    assert orders[1].priority == OrderPriority.LOW
    assert orders[2].priority == OrderPriority.HIGH


def test_should_handle_all_exceptions_in_full_flow(service, db_service, api_client):
    # Arrange
    user_id = 123
    orders = [
        Order(1, 'A', 100.0, False),
        Order(2, 'B', 150.0, True),
        Order(3, 'C', 250.0, False)
    ]
    db_service.get_orders_by_user.return_value = orders
    api_client.call_api.side_effect = APIException("Test API exception")
    
    # Act
    with patch('builtins.open', mock_open()):
        result = service.process_orders(user_id)
    
    # Assert
    assert result is True  # Main process should still return True
    assert orders[1].status == OrderStatus.API_FAILURE  # B order should have api_failure status


# Edge Cases

def test_should_process_orders_with_mixed_types_correctly(service, db_service, api_client):
    # Arrange
    user_id = 123
    orders = [
        Order(1, 'A', 100.0, False),
        Order(2, 'B', 150.0, True),
        Order(3, 'C', 250.0, False),
        Order(4, 'D', 300.0, True)  # Unknown type
    ]
    db_service.get_orders_by_user.return_value = orders
    api_client.call_api.return_value = APIResponse(APIStatus.SUCCESS, 60)
    
    # Act
    with patch('builtins.open', mock_open()):
        result = service.process_orders(user_id)
    
    # Assert
    assert result is True
    assert orders[0].status == OrderStatus.EXPORTED
    assert orders[1].status == OrderStatus.PENDING
    assert orders[2].status == OrderStatus.IN_PROGRESS
    assert orders[3].status == OrderStatus.UNKNOWN_TYPE


def test_should_process_orders_with_extreme_values_correctly(service, db_service):
    # Arrange
    user_id = 123
    orders = [
        Order(1, 'A', 0.0, False),  # Minimum amount
        Order(2, 'B', 999999.0, True),  # Very large amount
        Order(3, 'C', 201.0, False)  # Just above high priority threshold
    ]
    db_service.get_orders_by_user.return_value = orders
    
    # Act
    with patch('builtins.open', mock_open()):
        result = service.process_orders(user_id)
    
    # Assert
    assert result is True
    assert orders[0].priority == OrderPriority.LOW
    assert orders[1].priority == OrderPriority.HIGH
    assert orders[2].priority == OrderPriority.HIGH 
