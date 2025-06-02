# Accounting Ledger Model Context Protocol Server

A Model Context Protocol (MCP) server that provides accounting ledger creation, transaction and reporting capabilities using the [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) and [Python Accounting](https://github.com/ekmungai/python-accounting) library.

## Overview

This MCP server enables AI assistants to interact with a double-entry accounting system, allowing for:
- Creating accounting entities including the chart of accounts, currencies, and tax codes
- Recording various types of transactions (cash sales, cash purchases, supplier invoices, customer bills)
- Generating financial reports (profit & loss statements)

## Features

### 🏢 Entity Management
- Create accounting entities with default configuration (companies/organizations)

### 💰 Transaction Recording
- **Cash Sales**: Record immediate revenue transactions
- **Cash Purchases**: Record immediate expense transactions  
- **Client Invoices**: Create receivable transactions
- **Supplier Bills**: Create payable transactions

### 📊 Financial Reporting
- Generate profit & loss statements
- Customizable date ranges for reports

### 🔧 Built-in Tools
- Echo tool for testing connectivity
- Comprehensive error handling
- SQLite database backend

## Installation

This project uses [UV](https://docs.astral.sh/uv/) for dependency management. Make sure you have UV installed on your system.

### Prerequisites

Install uv

### Setup

1. **Clone the repository**:
   Clone this repository locally
   
2. **Create the virtual environment**:
   ```bash
   uv venv
   ```

3. **Activate the virtual environment**:
   ```bash
   source .venv/bin/activate
   ```

4. **Install dependencies**:
   ```bash
   uv sync
   ```

## Running the Server

### Development Mode

To run the server in development mode:

```bash
uv run mcp dev server.py
```

This will start the server the MCP Inspector which is a useful tool for testing and debugging the MCP server. To access the MCP Inspector navigate to `http://localhost:6274`.

### Testing in Claude Desktop

After installing Claude Desktop add the MCP server to it by running:

```bash
uv run mcp install server.py
```

After running this command open Claude Desktop. There will most likely be an error with the MCP server. Open Claude Desktop settings, navigate to Developer, select our MCP Server (My Ledger) and click Edit Config. Open the JSON configuration file and update the command and args values as shown (replacing path_to_server with the path to the server on your local machine).

```json
{
  "mcpServers": {
    "My Ledger": {
      "command": "/path_to_server/.venv/bin/python",
      "args": [
        "/path_to_server/server.py"
      ]
    }
  }
}
```

Now restart Claude Desktop and the MCP server should be working.

## Available Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `echo` | Test connectivity | `message: str` |
| `create_ledger` | Set up new accounting entity | `entity_name: str` |
| `record_cash_sale` | Record cash sale transaction | `narration: str, amount: float, quantity: int, tax_code: str, entity_name: str` |
| `record_cash_purchase` | Record cash purchase transaction | `narration: str, amount: float, quantity: int, tax_code: str, entity_name: str` |
| `record_client_invoice` | Create client invoice | `narration: str, amount: float, quantity: int, tax_code: str, entity_name: str` |
| `record_supplier_bill` | Create supplier bill | `narration: str, amount: float, quantity: int, tax_code: str, entity_name: str` |
| `generate_profit_loss_report` | Generate P&L report | `entity_name: str, start_date: str, end_date: str` |

## Configuration

The server uses a `config.toml` file for configuration. Key settings include:

- **Database**: SQLite database URL
- **Account Types**: Chart of accounts configuration
- **Transaction Types**: Available transaction types and prefixes
- **Tax Settings**: Default tax codes and rates
- **Reporting**: Report formatting and sections

## Database Schema

The system uses the Python Accounting library's database schema, which includes:

- **Entities**: Companies/organizations
- **Currencies**: Supported currencies
- **Accounts**: Chart of accounts with types
- **Taxes**: Tax codes and rates
- **Transactions**: Various transaction types
- **Line Items**: Transaction details

## Development

### Project Structure

```
mcpServerDemo/
├── server.py              # Main MCP server implementation
├── main.py                # Entry point
├── pyproject.toml         # UV project configuration
├── config.toml            # Accounting system configuration
├── test_accounting.db     # SQLite database
└── python_accounting/     # Local Python Accounting library
```

### Adding New Features

1. Add new tools to `server.py` using the `@mcp.tool()` decorator
2. Update the configuration in `config.toml` if needed
3. Test using the MCP Inspector
4. Update this README with new tool documentation

## Dependencies

- **mcp[cli]**: Model Context Protocol SDK
- **python-dateutil**: Date parsing utilities
- **sqlalchemy**: Database ORM
- **strenum**: String enumerations
- **toml**: Configuration file parsing

