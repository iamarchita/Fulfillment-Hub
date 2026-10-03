# Fulfillment Hub — Operations Control Center

Fulfillment Hub is an internal operations management application designed to help fulfillment teams monitor and manage orders, inventory, warehouse transfers, picking, packing, staging, shipping, and operational exceptions.

## Features

- Dashboard with key operational KPIs
- Order tracking and fulfillment timeline
- Priority and delayed order management
- Inventory visibility across warehouses
- Warehouse transfer management
- Picking and packing workflow
- Staging and shipping management
- Courier pickup and shipment tracking
- Exception management
- Operational notifications
- Reports and operational metrics
- User authentication and settings

## Tech Stack

- Python
- Flask
- MySQL
- mysql-connector-python
- HTML/CSS
- Bootstrap
- JavaScript

## Setup & Installation

### 1. Clone the Repository

```bash
git clone ---  https://github.com/iamarchita/Fulfillment-Hub
cd fulfillment-hub
If the repository contains a nested fulfillment-hub folder, enter that folder:

cd fulfillment-hub

Make sure you are in the directory containing app.py.

2. Create Virtual Environment
python -m venv venv

For Windows PowerShell:

venv\Scripts\activate

If PowerShell blocks script execution:

Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned

Then activate the environment again:

venv\Scripts\activate
3. Install Dependencies
pip install -r requirements.txt
Database Setup
4. Create the MySQL Database

Open MySQL Workbench and run the SQL file:

database/schema.sql

This creates the fulfillment_hub database, required tables, and seed data.

5. Create the Application Database User

Run the following in MySQL Workbench:

CREATE USER 'fulfillment_user'@'localhost'
IDENTIFIED BY 'YOUR_PASSWORD';

GRANT ALL PRIVILEGES ON fulfillment_hub.* 
TO 'fulfillment_user'@'localhost';

FLUSH PRIVILEGES;

Replace YOUR_PASSWORD with the password you choose.

Environment Configuration

The actual .env file is not included in the repository because it contains local database credentials.

Create a .env file in the same directory as app.py using .env.example as a template:

DB_HOST=localhost
DB_PORT=3306
DB_NAME=fulfillment_hub
DB_USER=fulfillment_user
DB_PASSWORD=YOUR_PASSWORD
SECRET_KEY=YOUR_SECRET_KEY

Use the same password configured for the MySQL application user.

Do not upload the actual .env file to GitHub.

Run the Application

Make sure MySQL is running and the virtual environment is activated.

Run:

python app.py

Open the application in your browser:

http://127.0.0.1:5000
Fulfillment Workflow

The application supports the following operational workflow:

Order Received
      ↓
Order Processing
      ↓
Inventory Check
      ↓
Picking
      ↓
Packing
      ↓
Staging
      ↓
Courier Pickup
      ↓
Shipped
      ↓
Delivered

Operational issues such as missing stock, wrong product or variant, damaged items, misplaced boxes, missed courier pickups, and delayed processing can be tracked through the Exceptions module.

Project Structure
fulfillment-hub/
│
├── app.py
├── config.py
├── requirements.txt
├── .env.example
├── README.md
│
├── database/
│   └── schema.sql
│
├── routes/
├── templates/
├── static/
└── utils/
Notes
MySQL must be running before starting the Flask application.
The database should be initialized using database/schema.sql.
A local .env file is required to connect the application to MySQL.
The actual .env file is intentionally excluded from the repository.
.env.example is provided as the configuration template.
The application is intended as an internal fulfillment operations tool rather than a customer-facing e-commerce storefront.
