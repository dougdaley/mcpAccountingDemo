from mcp.server.fastmcp import FastMCP
from sqlalchemy import create_engine, Engine
from python_accounting.config import config
from python_accounting.models import Base, Entity, Currency, Account, Tax, LineItem
from python_accounting.database.session import get_session
from python_accounting.transactions import CashSale, CashPurchase, ClientInvoice, SupplierBill
from python_accounting.reports import IncomeStatement
from datetime import datetime
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from dataclasses import dataclass
from decimal import Decimal
import json

mcp = FastMCP("My Ledger")
mcp = FastMCP("My Ledger", dependencies=["sqlalchemy", "python-dateutil", "strenum", "toml"])

@dataclass
class AppContext:
    engine: Engine  # SQLAlchemy engine

@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Manage application lifecycle for accounting engine."""
    database_config = config.database
    engine = create_engine(database_config["url"])
    Base.metadata.create_all(engine)
    try:
        yield AppContext(engine=engine)
    finally:
        # Place for engine cleanup if needed
        pass

mcp = FastMCP("My Ledger", lifespan=app_lifespan, dependencies=["sqlalchemy", "python-dateutil", "strenum", "toml"])

@mcp.tool()
async def echo(message: str) -> str:
    """
    Echoes the input message back to the user.

    Args:
        message (str): The message to echo.
    """
    return f"Your message: {message}"

@mcp.tool()
async def create_ledger(entity_name: str) -> str:
    """
    Sets up the ledger by:
    - Creating the SQLAlchemy engine from configuration.
    - Running migrations to create tables.
    - Creating a default reporting entity, currency, chart of accounts, and taxes if not present.
    """
    ctx = mcp.get_context()
    engine = ctx.request_context.lifespan_context.engine
    #Base.metadata.create_all(engine)
    with get_session(engine) as session:
        entity = session.query(Entity).filter_by(name=entity_name).first()
        if not entity:
            entity = Entity(name=entity_name)
            session.add(entity)
            session.commit()

            default_currency = Currency(name="Australian Dollars", code="AUD", entity_id=entity.id)
            session.add(default_currency)
            session.commit()

            accounts = [
                Account(name="Tax Account", account_type=Account.AccountType.CONTROL, currency_id=default_currency.id, entity_id=entity.id),
                Account(name="Bank Account", account_type=Account.AccountType.BANK, currency_id=default_currency.id, entity_id=entity.id),
                Account(name="Revenue Account", account_type=Account.AccountType.OPERATING_REVENUE, currency_id=default_currency.id, entity_id=entity.id),
                Account(name="Client Account", account_type=Account.AccountType.RECEIVABLE, currency_id=default_currency.id, entity_id=entity.id),
                Account(name="Supplier Account", account_type=Account.AccountType.PAYABLE, currency_id=default_currency.id, entity_id=entity.id),
                Account(name="Opex Account", account_type=Account.AccountType.OPERATING_EXPENSE, currency_id=default_currency.id, entity_id=entity.id),
                Account(name="Expense Account", account_type=Account.AccountType.DIRECT_EXPENSE, currency_id=default_currency.id, entity_id=entity.id),
                Account(name="Asset Account", account_type=Account.AccountType.NON_CURRENT_ASSET, currency_id=default_currency.id, entity_id=entity.id)
            ]
            session.add_all(accounts)
            session.commit()

            tax_account = accounts[0]
            output_tax = Tax(name="Output GST", code="GSTOUT", account_id=tax_account.id, rate=20, entity_id=entity.id)
            input_tax = Tax(name="Input GST", code="GSTIN", account_id=tax_account.id, rate=10, entity_id=entity.id)
            session.add_all([output_tax, input_tax])
            session.commit()

            return f"Successfully set up the accounting engine with entity '{entity_name}', default currency, accounts, and taxes."
        else:
            return f"Entity '{entity_name}' already exists. No changes made."

@mcp.tool()
async def record_cash_sale(
    narration: str, 
    amount: float, 
    quantity: int = 1,
    tax_code: str = "GSTOUT",
    entity_name: str = "Example Company"
) -> str:
    """
    Records a cash sale transaction.
    
    Args:
        narration: Description of the sale
        amount: Sale amount (excluding tax)
        quantity: Quantity of items sold
        tax_code: Tax code to apply (default: GSTOUT)
        entity_name: Entity name to use
    """
    ctx = mcp.get_context()
    engine = ctx.request_context.lifespan_context.engine
    
    with get_session(engine) as session:
        # Get the entity
        entity = session.query(Entity).filter_by(name=entity_name).first()
        if not entity:
            return f"Entity '{entity_name}' not found. Please create the ledger first."
        
        # Set the session entity for proper isolation
        session.entity = entity
        
        # Get required accounts
        bank_account = session.query(Account).filter_by(
            name="Bank Account", entity_id=entity.id
        ).first()
        revenue_account = session.query(Account).filter_by(
            name="Revenue Account", entity_id=entity.id
        ).first()
        tax = session.query(Tax).filter_by(
            code=tax_code, entity_id=entity.id
        ).first()
        
        if not bank_account or not revenue_account:
            return "Required accounts not found. Please set up the ledger first."
        
        # Convert amounts to Decimal for python_accounting library
        decimal_amount = Decimal(str(amount))
        decimal_quantity = Decimal(str(quantity))
        
        # Create cash sale transaction
        cash_sale = CashSale(
            narration=narration,
            transaction_date=datetime.now(),
            account_id=bank_account.id,
            entity_id=entity.id,
        )
        session.add(cash_sale)
        session.flush()
        
        # Create line item
        line_item = LineItem(
            narration=f"{narration} - Revenue",
            account_id=revenue_account.id,
            amount=decimal_amount,
            quantity=decimal_quantity,
            tax_id=tax.id if tax else None,
            entity_id=entity.id,
        )
        session.add(line_item)
        session.flush()
        
        # Add line item to transaction and post
        cash_sale.line_items.add(line_item)
        session.add(cash_sale)
        cash_sale.post(session)
        session.commit()
        
        total_amount = decimal_amount * decimal_quantity
        tax_amount = (total_amount * tax.rate / 100) if tax else Decimal('0')
        
        return f"Cash sale recorded: {narration}, Amount: {total_amount}, Tax: {tax_amount}, Total: {total_amount + tax_amount}"

@mcp.tool()
async def record_cash_purchase(
    narration: str,
    amount: float,
    quantity: int = 1,
    tax_code: str = "GSTIN",
    entity_name: str = "Example Company"
) -> str:
    """
    Records a cash purchase (expense) transaction.
    
    Args:
        narration: Description of the purchase
        amount: Purchase amount (excluding tax)
        quantity: Quantity of items purchased
        tax_code: Tax code to apply (default: GSTIN)
        entity_name: Entity name to use
    """
    ctx = mcp.get_context()
    engine = ctx.request_context.lifespan_context.engine
    
    with get_session(engine) as session:
        # Get the entity
        entity = session.query(Entity).filter_by(name=entity_name).first()
        if not entity:
            return f"Entity '{entity_name}' not found. Please create the ledger first."
        
        # Set the session entity for proper isolation
        session.entity = entity
        
        # Get required accounts
        bank_account = session.query(Account).filter_by(
            name="Bank Account", entity_id=entity.id
        ).first()
        expense_account = session.query(Account).filter_by(
            name="Opex Account", entity_id=entity.id
        ).first()
        tax = session.query(Tax).filter_by(
            code=tax_code, entity_id=entity.id
        ).first()
        
        if not bank_account or not expense_account:
            return "Required accounts not found. Please set up the ledger first."
        
        # Convert amounts to Decimal for python_accounting library
        decimal_amount = Decimal(str(amount))
        decimal_quantity = Decimal(str(quantity))
        
        # Create cash purchase transaction
        cash_purchase = CashPurchase(
            narration=narration,
            transaction_date=datetime.now(),
            account_id=bank_account.id,
            entity_id=entity.id,
        )
        session.add(cash_purchase)
        session.flush()
        
        # Create line item
        line_item = LineItem(
            narration=f"{narration} - Expense",
            account_id=expense_account.id,
            amount=decimal_amount,
            quantity=decimal_quantity,
            tax_id=tax.id if tax else None,
            entity_id=entity.id,
        )
        session.add(line_item)
        session.flush()
        
        # Add line item to transaction and post
        cash_purchase.line_items.add(line_item)
        session.add(cash_purchase)
        cash_purchase.post(session)
        session.commit()
        
        total_amount = decimal_amount * decimal_quantity
        tax_amount = (total_amount * tax.rate / 100) if tax else Decimal('0')
        
        return f"Cash purchase recorded: {narration}, Amount: {total_amount}, Tax: {tax_amount}, Total: {total_amount + tax_amount}"

@mcp.tool()
async def record_client_invoice(
    narration: str,
    amount: float,
    quantity: int = 1,
    tax_code: str = "GSTOUT",
    entity_name: str = "Example Company"
) -> str:
    """
    Records a client invoice (credit sale) transaction.
    
    Args:
        narration: Description of the invoice
        amount: Invoice amount (excluding tax)
        quantity: Quantity of items invoiced
        tax_code: Tax code to apply (default: GSTOUT)
        entity_name: Entity name to use
    """
    ctx = mcp.get_context()
    engine = ctx.request_context.lifespan_context.engine
    
    with get_session(engine) as session:
        # Get the entity
        entity = session.query(Entity).filter_by(name=entity_name).first()
        if not entity:
            return f"Entity '{entity_name}' not found. Please create the ledger first."
        
        # Set the session entity for proper isolation
        session.entity = entity
        
        # Get required accounts
        client_account = session.query(Account).filter_by(
            name="Client Account", entity_id=entity.id
        ).first()
        revenue_account = session.query(Account).filter_by(
            name="Revenue Account", entity_id=entity.id
        ).first()
        tax = session.query(Tax).filter_by(
            code=tax_code, entity_id=entity.id
        ).first()
        
        if not client_account or not revenue_account:
            return "Required accounts not found. Please set up the ledger first."
        
        # Convert amounts to Decimal for python_accounting library
        decimal_amount = Decimal(str(amount))
        decimal_quantity = Decimal(str(quantity))
        
        # Create client invoice transaction
        client_invoice = ClientInvoice(
            narration=narration,
            transaction_date=datetime.now(),
            account_id=client_account.id,
            entity_id=entity.id,
        )
        session.add(client_invoice)
        session.flush()
        
        # Create line item
        line_item = LineItem(
            narration=f"{narration} - Revenue",
            account_id=revenue_account.id,
            amount=decimal_amount,
            quantity=decimal_quantity,
            tax_id=tax.id if tax else None,
            entity_id=entity.id,
        )
        session.add(line_item)
        session.flush()
        
        # Add line item to transaction and post
        client_invoice.line_items.add(line_item)
        session.add(client_invoice)
        client_invoice.post(session)
        session.commit()
        
        total_amount = decimal_amount * decimal_quantity
        tax_amount = (total_amount * tax.rate / 100) if tax else Decimal('0')
        
        return f"Client invoice recorded: {narration}, Amount: {total_amount}, Tax: {tax_amount}, Total: {total_amount + tax_amount}"

@mcp.tool()
async def record_supplier_bill(
    narration: str,
    amount: float,
    quantity: int = 1,
    tax_code: str = "GSTIN",
    entity_name: str = "Example Company"
) -> str:
    """
    Records a supplier bill (credit purchase) transaction.
    
    Args:
        narration: Description of the bill
        amount: Bill amount (excluding tax)
        quantity: Quantity of items billed
        tax_code: Tax code to apply (default: GSTIN)  
        entity_name: Entity name to use
    """
    ctx = mcp.get_context()
    engine = ctx.request_context.lifespan_context.engine
    
    with get_session(engine) as session:
        # Get the entity
        entity = session.query(Entity).filter_by(name=entity_name).first()
        if not entity:
            return f"Entity '{entity_name}' not found. Please create the ledger first."
        
        # Set the session entity for proper isolation
        session.entity = entity
        
        # Get required accounts
        supplier_account = session.query(Account).filter_by(
            name="Supplier Account", entity_id=entity.id
        ).first()
        expense_account = session.query(Account).filter_by(
            name="Opex Account", entity_id=entity.id
        ).first()
        tax = session.query(Tax).filter_by(
            code=tax_code, entity_id=entity.id
        ).first()
        
        if not supplier_account or not expense_account:
            return "Required accounts not found. Please set up the ledger first."
        
        # Convert amounts to Decimal for python_accounting library
        decimal_amount = Decimal(str(amount))
        decimal_quantity = Decimal(str(quantity))
        
        # Create supplier bill transaction
        supplier_bill = SupplierBill(
            narration=narration,
            transaction_date=datetime.now(),
            account_id=supplier_account.id,
            entity_id=entity.id,
        )
        session.add(supplier_bill)
        session.flush()
        
        # Create line item
        line_item = LineItem(
            narration=f"{narration} - Expense",
            account_id=expense_account.id,
            amount=decimal_amount,
            quantity=decimal_quantity,
            tax_id=tax.id if tax else None,
            entity_id=entity.id,
        )
        session.add(line_item)
        session.flush()
        
        # Add line item to transaction and post
        supplier_bill.line_items.add(line_item)
        session.add(supplier_bill)
        supplier_bill.post(session)
        session.commit()
        
        total_amount = decimal_amount * decimal_quantity
        tax_amount = (total_amount * tax.rate / 100) if tax else Decimal('0')
        
        return f"Supplier bill recorded: {narration}, Amount: {total_amount}, Tax: {tax_amount}, Total: {total_amount + tax_amount}"

@mcp.tool()
async def generate_profit_loss_report(
    entity_name: str = "Example Company",
    start_date: str = "",
    end_date: str = ""
) -> str:
    """
    Generates a Profit & Loss (Income Statement) report in JSON format.
    
    Args:
        entity_name: Entity name to generate report for
        start_date: Start date for the report (YYYY-MM-DD format, optional)
        end_date: End date for the report (YYYY-MM-DD format, optional)
    
    Returns:
        JSON string containing the P&L report
    """
    ctx = mcp.get_context()
    engine = ctx.request_context.lifespan_context.engine
    
    with get_session(engine) as session:
        # Get the entity
        entity = session.query(Entity).filter_by(name=entity_name).first()
        if not entity:
            return json.dumps({
                "error": f"Entity '{entity_name}' not found. Please create the ledger first."
            })
        
        # Set the session entity for proper isolation
        session.entity = entity
        
        # Parse dates if provided
        parsed_start_date = None
        parsed_end_date = None
        
        if start_date and start_date.strip():
            try:
                parsed_start_date = datetime.strptime(start_date, "%Y-%m-%d")
            except ValueError:
                return json.dumps({
                    "error": "Invalid start_date format. Use YYYY-MM-DD."
                })
        
        if end_date and end_date.strip():
            try:
                parsed_end_date = datetime.strptime(end_date, "%Y-%m-%d")
            except ValueError:
                return json.dumps({
                    "error": "Invalid end_date format. Use YYYY-MM-DD."
                })
        
        try:
            # Generate the Income Statement
            income_statement = IncomeStatement(session, parsed_start_date, parsed_end_date)
            
            return income_statement.printout
            
        except Exception as e:
            return json.dumps({
                "error": f"Failed to generate P&L report: {str(e)}"
            })

if __name__ == "__main__":
    mcp.run(transport="stdio")