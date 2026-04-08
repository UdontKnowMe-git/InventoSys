# test_service.py
# use command: pytest test_service.py -v --cov=backend/service --cov-report=term-missing --cov-fail-under=85
import pytest
from unittest.mock import MagicMock, patch, Mock
from backend.service import InventoryService

@pytest.fixture
def mock_service():
    with patch('backend.service.DatabaseManager') as MockDB:
        mock_db = MockDB.return_value
        service = InventoryService()
        service.db = mock_db  # Replace the real DB AFTER init
        return service, mock_db

def test_add_product_valid(mock_service):
    service, mock_db = mock_service
    mock_db.execute_query.return_value = True  # DB insert succeeds
    
    success, msg = service.add_product("SKU001", "Widget A", 5.0, 10.0, 20)
    
    assert success is True
    assert "Product added" in msg
    mock_db.execute_query.assert_called_once_with(
        "INSERT INTO products (sku, name, stockqty, unitcost, retailprice, minstock) VALUES (?, ?, 0, ?, ?, ?)",
        ("SKU001", "Widget A", 5.0, 10.0, 20),
        is_read=False
    )

def test_add_product_invalid_price(mock_service):
    service, _ = mock_service
    
    success, msg = service.add_product("SKU001", "Widget A", 0, 10.0, 20)
    
    assert success is False
    assert "price/cost cannot be negative" in msg
    # No DB call for validation failure

def test_add_product_no_sku(mock_service):
    service, _ = mock_service
    
    success, msg = service.add_product("", "Widget A", 5.0, 10.0, 20)
    
    assert success is False
    assert "SKU and Name are required" in msg

def test_process_transaction_insufficient_stock(mock_service):
    service, mock_db = mock_service
    mock_db.execute_query.return_value = [[1, 10, "Widget A", 20]]  # id=1, stock=10, min=20
    
    success, msg = service.process_transaction("SKU001", "OUT", 15)
    
    assert success is False
    assert "Insufficient stock" in msg

def test_process_transaction_low_stock_alert(mock_service):
    service, mock_db = mock_service
    mock_db.execute_query.side_effect = [  # First call: get product, Second: update stock
        [[1, 25, "Widget A", 20]],  # current=25, min=20
        True  # update succeeds
    ]
    
    success, msg = service.process_transaction("SKU001", "OUT", 7)  # 25-7=18 <20
    
    assert success is True
    assert "LOW STOCK ALERT" in msg

def test_process_transaction_stock_in(mock_service):
    service, mock_db = mock_service
    mock_db.execute_query.side_effect = [
        [[1, 10, "Widget A", 20]],  # current=10
        True  # update succeeds
    ]
    
    success, msg = service.process_transaction("SKU001", "IN", 5)  # 10+5=15
    
    assert success is True
    assert "Transaction recorded" in msg or "LOW STOCK ALERT" in msg

def test_login_valid(mock_service):
    service, mock_db = mock_service
    mock_db.fetch_one.return_value = ("Admin",)  # Note: tuple with role string
    
    success, role = service.login_user("admin", "pass")
    
    assert success is True
    assert role == "Admin"

def test_login_invalid(mock_service):
    service, mock_db = mock_service
    mock_db.fetch_one.return_value = None
    
    success, role = service.login_user("admin", "wrong")
    
    assert success is False
    assert role is None

def test_delete_user_self_protection(mock_service):
    service, mock_db = mock_service
    
    success, msg = service.delete_user("currentuser", "currentuser")
    
    assert success is False
    assert "You cannot delete yourself" in msg