import csv
import time
from typing import Any, List, Optional
from abc import ABC, abstractmethod

# Order Status Constants
class OrderStatus:
	NEW = 'new'
	PENDING = 'pending'
	PROCESSED = 'processed'
	IN_PROGRESS = 'in_progress'
	COMPLETED = 'completed'
	UNKNOWN_TYPE = 'unknown_type'
	ERROR = 'error'
	EXPORTED = 'exported'
	EXPORT_FAILED = 'export_failed'
	API_ERROR = 'api_error'
	API_FAILURE = 'api_failure'
	DB_ERROR = 'db_error'

# Order Priority Constants
class OrderPriority:
	HIGH = 'high'
	LOW = 'low'

# API Status Constants
class APIStatus:
	SUCCESS = 'success'
	ERROR = 'error'

class Order:
	def __init__(self, id: int, type: str, amount: float, flag: bool):
		self.id = id
		self.type = type
		self.amount = amount
		self.flag = flag
		self.status = OrderStatus.NEW
		self.priority = OrderPriority.LOW

class APIResponse:
	def __init__(self, status: str, data: Any):
		self.status = status
		self.data = data

class APIException(Exception):
	pass

class DatabaseException(Exception):
	pass


class DatabaseService(ABC):
	@abstractmethod
	def get_orders_by_user(self, user_id: int) -> List[Order]:
		pass

	@abstractmethod
	def update_order_status(self, order_id: int, status: str, priority: str) -> bool:
		pass


class APIClient(ABC):
	@abstractmethod
	def call_api(self, order_id: int) -> APIResponse:
		pass

class OrderProcessingService:
	def __init__(self, db_service: DatabaseService, api_client: APIClient):
		self.db_service = db_service
		self.api_client = api_client

	def process_orders(self, user_id: int) -> bool:
		"""Process all orders for a given user."""
		try:
			orders = self.db_service.get_orders_by_user(user_id)
			if not orders:
				return False

			csv_file = self._create_csv_file(user_id)
			for order in orders:
				self._process_single_order(order, csv_file)
			return True
		except Exception:
			return False

	def _create_csv_file(self, user_id: int) -> str:
		"""Create a new CSV file for type A orders and write the header."""
		csv_file = f'orders_type_A_{user_id}_{int(time.time())}.csv'
		with open(csv_file, 'w', newline='') as file_handle:
			writer = csv.writer(file_handle)
			writer.writerow(['ID', 'Type', 'Amount', 'Flag', 'Status', 'Priority'])
			
		return csv_file
	
	def _process_single_order(self, order: Order, csv_file: str) -> None:
		"""Process a single order based on its type."""
		self._process_order_by_type(order, csv_file)
		self._update_order_priority(order)
		self._save_order_status(order)
	
	def _process_order_by_type(self, order: Order, csv_file: str) -> None:
		"""Process order based on its type (A, B, C, or other)."""
		if order.type == 'A':
			self._process_type_a_order(order, csv_file)
		elif order.type == 'B':
			self._process_type_b_order(order)
		elif order.type == 'C':
			self._process_type_c_order(order)
		else:
			order.status = OrderStatus.UNKNOWN_TYPE
	
	def _process_type_a_order(self, order: Order, csv_file: str) -> None:
		"""Process type A order by exporting it to CSV."""
		try:
			with open(csv_file, 'a', newline='') as file_handle:
				writer = csv.writer(file_handle)
				writer.writerow([
					order.id,
					order.type,
					order.amount,
					str(order.flag).lower(),
					order.status,
					order.priority
				])

				if order.amount > 150:
					writer.writerow(['', '', '', '', 'Note', 'High value order'])

			order.status = OrderStatus.EXPORTED
		except IOError:
			order.status = OrderStatus.EXPORT_FAILED
	
	def _process_type_b_order(self, order: Order) -> None:
		"""Process type B order by calling the API and updating status based on response."""
		try:
			api_response = self.api_client.call_api(order.id)

			if api_response.status == APIStatus.SUCCESS:
				if api_response.data >= 50 and order.amount < 100:
					order.status = OrderStatus.PROCESSED
				elif api_response.data < 50 or order.flag:
					order.status = OrderStatus.PENDING
				else:
					order.status = OrderStatus.ERROR
			else:
				order.status = OrderStatus.API_ERROR
		except APIException:
			order.status = OrderStatus.API_FAILURE
	
	def _process_type_c_order(self, order: Order) -> None:
		"""Process type C order by setting status based on flag."""
		if order.flag:
			order.status = OrderStatus.COMPLETED
		else:
			order.status = OrderStatus.IN_PROGRESS
	
	def _update_order_priority(self, order: Order) -> None:
		"""Update order priority based on amount."""
		if order.amount > 200:
			order.priority = OrderPriority.HIGH
		else:
			order.priority = OrderPriority.LOW
	
	def _save_order_status(self, order: Order) -> None:
		"""Save the updated order status and priority to the database."""
		try:
			self.db_service.update_order_status(order.id, order.status, order.priority)
		except DatabaseException:
			order.status = OrderStatus.DB_ERROR
