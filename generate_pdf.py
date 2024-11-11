import xmlrpc.client
from fpdf import FPDF
from datetime import datetime, timedelta
import sys

url = 'http://137.184.137.192:8069/'
db = 'odoo'
username = 'rickyrichpos2023@gmail.com'
password = 'fabian@7167O'

common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(url))
uid = common.authenticate(db, username, password, {})
models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(url))

def format_currency(value):
    return f"${value:,.2f}"

def get_session_data(session_name):
    try:
        session_id = models.execute_kw(db, uid, password, 'pos.session', 'search', [[['name', '=', session_name]]])
        if not session_id:
            raise ValueError("Session not found")
        session_data = models.execute_kw(db, uid, password, 'pos.session', 'read', [session_id])
        return session_data[0]
    except Exception as e:
        print(f"Error fetching session data: {e}")
        sys.exit(1)

def list_statement_line_fields():
    fields = models.execute_kw(db, uid, password, 'account.bank.statement.line', 'fields_get', [], {'attributes': ['string', 'type']})
    for field, details in fields.items():
        print(f"{field}: {details['string']} ({details['type']}")

def get_cash_movements(session_id):
    cash_in = []
    cash_out = []
    statement_lines = models.execute_kw(db, uid, password, 'account.bank.statement.line', 'search_read', [[['pos_session_id', '=', session_id]]], {'fields': ['amount', 'journal_id', 'payment_ref', 'ref', 'narration']})
    for line in statement_lines:
        if 'POS/' in line['payment_ref'] and '-' in line['payment_ref']:
            payment_ref = line['payment_ref'].split('-')[-1].strip()
            movement = {
                'amount': line['amount'],
                'payment_ref': payment_ref or 'Sin descripción',
            }
            if line['amount'] > 0:
                cash_in.append(movement)
            else:
                cash_out.append(movement)
    return cash_in, cash_out

def get_sales_by_payment_method(session_id):
    orders = models.execute_kw(db, uid, password, 'pos.order', 'search_read', [[['session_id', '=', session_id]]], {'fields': ['amount_total', 'payment_ids']})
    cash_sales = 0
    other_sales = 0

    for order in orders:
        payments = models.execute_kw(db, uid, password, 'pos.payment', 'read', [order['payment_ids']], {'fields': ['amount', 'payment_method_id']})
        for payment in payments:
            if payment['payment_method_id'][1] == 'Efectivo':
                cash_sales += payment['amount']
            else:
                other_sales += payment['amount']

    return cash_sales, other_sales

def generate_pdf(session_data):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)

        pos_name = session_data['config_id'][1].split(' ')[0]
        date = datetime.strptime(session_data['start_at'], '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d')
        filename = f"{pos_name}_{date}.pdf"
        
        cash_in, cash_out = get_cash_movements(session_data['id'])
        cash_sales, other_sales = get_sales_by_payment_method(session_data['id'])

        pdf.cell(200, 10, txt=f"{pos_name} - {date}", ln=True, align='C')
        pdf.cell(200, 10, txt=f"Saldo inicial: {format_currency(session_data['cash_register_balance_start'])}", ln=True)
        pdf.cell(200, 10, txt=f"Ventas en efectivo: {format_currency(cash_sales)}", ln=True)
        
        pdf.cell(200, 10, txt="Ingresos en efectivo (cash in):", ln=True)
        for movement in cash_in:
            pdf.cell(200, 10, txt=f"   {movement['payment_ref']}: {format_currency(movement['amount'])}", ln=True)
        
        pdf.cell(200, 10, txt="Retiradas de efectivo (cash out):", ln=True)
        for movement in cash_out:
            pdf.cell(200, 10, txt=f"   {movement['payment_ref']}: {format_currency(movement['amount'])}", ln=True)
        
        pdf.cell(200, 10, txt=f"Efectivo en caja: {format_currency(session_data['cash_register_balance_end_real'])}", ln=True)
        pdf.cell(200, 10, txt=f"Diferencia en cierre: {format_currency(session_data['cash_register_difference'])}", ln=True)
        pdf.cell(200, 10, txt=f"Total de ventas: {format_currency(session_data['total_payments_amount'])}", ln=True)
        pdf.cell(200, 10, txt=f"Ventas en efectivo: {format_currency(cash_sales)}", ln=True)
        pdf.cell(200, 10, txt=f"Otras ventas: {format_currency(other_sales)}", ln=True)

        pdf.output(filename)
        print(filename)  # Ensure only the filename is printed
    except Exception as e:
        print(f"Error generating PDF: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python main.py <POS_NAME>")
        sys.exit(1)
    
    pos_name = sys.argv[1]
    try:
        session_data = get_session_data(pos_name)
        generate_pdf(session_data)
    except ValueError as e:
        print(e)
        sys.exit(1)