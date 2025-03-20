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
    return f"${int(value):,}"  # Changed to show integers without decimals

def format_date_spanish(date_str):
    """Format date as 'DD de Month del YYYY' in Spanish"""
    if not date_str:
        return ""
    
    date_obj = None
    if isinstance(date_str, str):
        # Try to parse the string to a datetime object
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            try:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            except ValueError:
                return date_str  # Return original if parsing fails
    elif isinstance(date_str, datetime):
        date_obj = date_str
    else:
        return str(date_str)  # Return string representation if not a recognized type
    
    # Spanish month names
    spanish_months = [
        "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", 
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
    ]
    
    day = date_obj.day
    month = spanish_months[date_obj.month - 1]  # Adjust for 0-based index
    year = date_obj.year
    
    return f"{day:02d} de {month} del {year}"

def adjust_time(dt_string, format_in='%Y-%m-%d %H:%M:%S'):
    """Adjust datetime by -5 hours and format in 12-hour AM/PM format"""
    dt = datetime.strptime(dt_string, format_in)
    adjusted_dt = dt - timedelta(hours=5)
    return adjusted_dt.strftime('%I:%M:%S %p')  # 12-hour format with AM/PM

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
    
    # Track each payment method separately including cash
    payment_method_totals = {}

    for order in orders:
        payments = models.execute_kw(db, uid, password, 'pos.payment', 'read', [order['payment_ids']], {'fields': ['amount', 'payment_method_id']})
        for payment in payments:
            method_name = payment['payment_method_id'][1]
            method_amount = payment['amount']
            
            if method_name not in payment_method_totals:
                payment_method_totals[method_name] = 0
            payment_method_totals[method_name] += method_amount

    # Sort payment methods, but ensure cash comes first if present
    cash_amount = payment_method_totals.pop('Efectivo', 0)
    sorted_methods = sorted(payment_method_totals.items())
    
    # Put cash back at the beginning of the list
    if cash_amount > 0:
        sorted_methods = [('Efectivo', cash_amount)] + sorted_methods
    
    return sorted_methods, sum(payment_method_totals.values()), cash_amount

def get_stock_movements(session_id):
    """Get stock movements for products related to this session"""
    # First, get the session details to find the related location/warehouse
    session_data = models.execute_kw(db, uid, password, 'pos.session', 'read', 
                                    [session_id], 
                                    {'fields': ['config_id', 'start_at', 'stop_at']})
    
    if not session_data:
        return []
    
    # Get the POS config to find its stock location
    pos_config_id = session_data[0]['config_id'][0]
    pos_config = models.execute_kw(db, uid, password, 'pos.config', 'read', 
                                  [pos_config_id], 
                                  {'fields': ['picking_type_id']})
    
    if not pos_config or not pos_config[0].get('picking_type_id'):
        return []
    
    # Get the picking type to find its location
    picking_type_id = pos_config[0]['picking_type_id'][0]
    picking_type = models.execute_kw(db, uid, password, 'stock.picking.type', 'read',
                                   [picking_type_id],
                                   {'fields': ['default_location_src_id']})
    
    if not picking_type or not picking_type[0].get('default_location_src_id'):
        return []
    
    # Get the stock location associated with this POS through its picking type
    pos_location_id = picking_type[0]['default_location_src_id'][0]
    
    # Session time boundaries
    start_time = session_data[0]['start_at']
    end_time = session_data[0]['stop_at'] or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    print(f"Analyzing inventory movements for location {pos_location_id} between {start_time} and {end_time}")
    
    # Get orders from this session for sales calculation
    orders = models.execute_kw(db, uid, password, 'pos.order', 'search_read', 
                              [[['session_id', '=', session_id]]], 
                              {'fields': ['id', 'name']})
    order_ids = [order['id'] for order in orders]
    order_names = [order['name'] for order in orders]
    
    # Get all stock moves affecting our location during the session period
    stock_moves = models.execute_kw(
        db, uid, password, 'stock.move', 'search_read',
        [[
            '|',  # OR condition for source or destination being our location
            ['location_id', '=', pos_location_id],
            ['location_dest_id', '=', pos_location_id],
            ['state', '=', 'done'],  # Only completed moves
            ['date', '>=', start_time],
            ['date', '<=', end_time]
        ]],
        {'fields': ['product_id', 'product_qty', 'location_id', 'location_dest_id', 'picking_id', 'origin', 'name']}
    )
    
    print(f"Found {len(stock_moves)} stock moves in the period")
    
    # Get all products that had movement during the session
    all_product_ids = set()
    for move in stock_moves:
        all_product_ids.add(move['product_id'][0])
    
    # Add products from POS orders
    lines = []
    if order_ids:
        lines = models.execute_kw(db, uid, password, 'pos.order.line', 'search_read',
                                [[['order_id', 'in', order_ids]]], 
                                {'fields': ['product_id', 'qty']})
        for line in lines:
            all_product_ids.add(line['product_id'][0])
    
    # Initialize product movement tracking
    product_movements = {}
    for product_id in all_product_ids:
        # Get product name
        product_info = models.execute_kw(db, uid, password, 'product.product', 'read',
                                       [product_id], {'fields': ['name', 'default_code']})
        if not product_info:
            continue
            
        product_name = product_info[0]['name']
        if product_info[0].get('default_code'):
            product_name = f"[{product_info[0]['default_code']}] {product_name}"
            
        product_movements[product_id] = {
            'product_id': product_id, 
            'product_name': product_name,
            'sold_qty': 0,
            'entries': 0,
            'exits': 0
        }
    
    # Calculate sales from POS orders
    for line in lines:
        product_id = line['product_id'][0]
        if product_id in product_movements:
            product_movements[product_id]['sold_qty'] += line['qty']
    
    # Analyze each stock move to categorize as entry or exit
    for move in stock_moves:
        product_id = move['product_id'][0]
        if product_id not in product_movements:
            continue
        
        # Check if this move is related to a POS order (to avoid double counting)
        is_pos_related = False
        if move.get('origin'):
            for order_name in order_names:
                if order_name in move.get('origin', ''):
                    is_pos_related = True
                    break
        
        # Skip POS-related movements as they're already counted in sales
        if is_pos_related:
            continue
            
        # If destination is our location, it's an entry
        if move['location_dest_id'][0] == pos_location_id:
            product_movements[product_id]['entries'] += move['product_qty']
            
        # If source is our location, it's an exit
        if move['location_id'][0] == pos_location_id:
            product_movements[product_id]['exits'] += move['product_qty']
    
    # Get current stock levels for all affected products
    stock_info = []
    for product_id, movement in product_movements.items():
        # Skip products with no actual movement
        if movement['sold_qty'] == 0 and movement['entries'] == 0 and movement['exits'] == 0:
            continue
            
        # Get current stock from the specific location
        quants = models.execute_kw(db, uid, password, 'stock.quant', 'search_read',
                                 [[['product_id', '=', product_id], 
                                   ['location_id', '=', pos_location_id]]],
                                 {'fields': ['quantity']})
        
        current_stock = sum(q['quantity'] for q in quants) if quants else 0
        
        # Calculate initial stock by accounting for all movements
        initial_stock = current_stock + movement['sold_qty'] - movement['entries'] + movement['exits']
        
        stock_info.append({
            'product_name': movement['product_name'],
            'initial_stock': initial_stock,
            'sales': -movement['sold_qty'],  # Negative because sales reduce stock
            'entries': movement['entries'],  # Positive for incoming
            'exits': -movement['exits'],     # Negative for outgoing
            'current_stock': current_stock
        })
    
    # Sort by product name for better readability
    stock_info.sort(key=lambda x: x['product_name'])
    return stock_info

def get_sales_details(session_id):
    """Get detailed sales information for this session"""
    orders = models.execute_kw(db, uid, password, 'pos.order', 'search_read', 
                              [[['session_id', '=', session_id]]], 
                              {'fields': ['id', 'name', 'date_order', 'amount_total', 'payment_ids']})
    
    sales_details = []
    for order in orders:
        order_lines = models.execute_kw(db, uid, password, 'pos.order.line', 'search_read',
                                       [[['order_id', '=', order['id']]]], 
                                       {'fields': ['product_id', 'qty', 'price_unit', 'price_subtotal']})
        
        # Get payment method information
        payment_methods = []
        if order['payment_ids']:
            payments = models.execute_kw(db, uid, password, 'pos.payment', 'read', 
                                        [order['payment_ids']], 
                                        {'fields': ['amount', 'payment_method_id']})
            
            # Group payments by method
            payment_by_method = {}
            for payment in payments:
                method_name = payment['payment_method_id'][1]
                if method_name not in payment_by_method:
                    payment_by_method[method_name] = []
                payment_by_method[method_name].append(payment['amount'])
            
            # Process each payment method
            for method, amounts in payment_by_method.items():
                if method == 'Efectivo' and len(amounts) > 1:
                    # For cash payments, calculate total paid and change
                    total_paid = sum(amount for amount in amounts if amount > 0)
                    change = abs(sum(amount for amount in amounts if amount < 0))
                    net_amount = total_paid - change
                    
                    payment_methods.append({
                        'method': 'Efectivo',
                        'amount': net_amount,
                        'is_cash': True,
                        'paid': total_paid,
                        'change': change
                    })
                else:
                    # For other payment methods or simple cash payments
                    payment_methods.append({
                        'method': method,
                        'amount': sum(amounts),
                        'is_cash': False
                    })
        
        # Format the order date with timezone adjustment
        order_time = adjust_time(order['date_order'])
        
        # Check if this is a refund order
        is_refund = 'REEMBOLSO' in order['name']
        
        sales_details.append({
            'order_name': order['name'],
            'order_date': order_time,
            'order_amount': order['amount_total'],
            'lines': order_lines,
            'payments': payment_methods,
            'is_refund': is_refund
        })
    
    return sales_details

def generate_pdf(session_data):
    try:
        pdf = FPDF()
        
        # First page - Cash information with improved layout
        pdf.add_page()
        
        # Header with POS name and date - Trim the name at the parenthesis
        full_pos_name = session_data['config_id'][1]
        pos_name = full_pos_name.split('(')[0].strip()  # Get text before the parenthesis and trim whitespace
        
        # Format the date in Spanish style: "01 de Enero del 2025"
        date_obj = datetime.strptime(session_data['start_at'], '%Y-%m-%d %H:%M:%S')
        date = format_date_spanish(date_obj)
        filename = f"{pos_name.replace(' ', '_')}_{date_obj.strftime('%Y-%m-%d')}.pdf"
        
        # Add a nice header
        pdf.set_font("Arial", 'B', 16)
        pdf.set_fill_color(220, 220, 220)  # Light gray background
        pdf.cell(0, 15, "REPORTE DE CIERRE DE CAJA", 1, 1, 'C', True)
        pdf.ln(5)
        
        # Add session info with full POS name
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(95, 10, f"Punto de Venta: {pos_name}", 0, 0, 'L')
        pdf.cell(95, 10, f"Fecha: {date}", 0, 1, 'R')
        
        # Session open/close times with timezone adjustment
        session_start = adjust_time(session_data['start_at'])
        session_end = "En curso"
        if session_data.get('stop_at'):
            session_end = adjust_time(session_data['stop_at'])
        
        pdf.set_font("Arial", '', 10)
        pdf.cell(95, 8, f"Hora de apertura: {session_start}", 0, 0, 'L')
        pdf.cell(95, 8, f"Hora de cierre: {session_end}", 0, 1, 'R')
        pdf.ln(5)
        
        # Get data
        cash_in, cash_out = get_cash_movements(session_data['id'])
        sorted_methods, other_sales, cash_sales = get_sales_by_payment_method(session_data['id'])

        # Cash summary section
        pdf.set_font("Arial", 'B', 14)
        pdf.set_fill_color(240, 240, 240)  # Very light gray background
        pdf.cell(0, 10, "RESUMEN DE EFECTIVO", 1, 1, 'C', True)
        pdf.ln(2)
        
        # Create a table for initial and final cash balance
        pdf.set_font("Arial", 'B', 11)
        
        # Initial balance row - no background fill
        pdf.cell(100, 10, "Saldo inicial:", 1, 0, 'L')
        pdf.cell(90, 10, f"{format_currency(session_data['cash_register_balance_start'])}", 1, 1, 'R')
        
        # Add opening difference (theoretical - real opening balance)
        opening_diff = session_data.get('cash_register_balance_start_difference', 0)
        has_opening_diff = opening_diff != 0
        if has_opening_diff:
            pdf.set_fill_color(255, 200, 200)  # Light red for difference
            pdf.cell(100, 10, "Diferencia de apertura:", 1, 0, 'L', has_opening_diff)
            pdf.cell(90, 10, f"{format_currency(opening_diff)}", 1, 1, 'R', has_opening_diff)
        
        # Final balance row - no background fill
        pdf.cell(100, 10, "Saldo final:", 1, 0, 'L')
        pdf.cell(90, 10, f"{format_currency(session_data['cash_register_balance_end_real'])}", 1, 1, 'R')
        
        # Difference row with conditional highlighting
        has_difference = session_data['cash_register_difference'] != 0
        if has_difference:
            pdf.set_fill_color(255, 200, 200)  # Light red for difference
        
        pdf.cell(100, 10, "Diferencia en cierre:", 1, 0, 'L', has_difference)
        pdf.cell(90, 10, f"{format_currency(session_data['cash_register_difference'])}", 1, 1, 'R', has_difference)
        
        # Improved Cash movements section with better visual separation
        pdf.ln(5)
        pdf.set_font("Arial", 'B', 12)
        pdf.set_fill_color(230, 245, 230)  # Light green for cash in
        pdf.cell(0, 10, "INGRESOS EN EFECTIVO", 1, 1, 'C', True)
        
        # Cash in section with improved layout
        if cash_in:
            pdf.set_font("Arial", 'B', 10)
            # Table header
            pdf.cell(100, 8, "Concepto", 1, 0, 'C')
            pdf.cell(90, 8, "Monto", 1, 1, 'C')
            
            # Table rows
            pdf.set_font("Arial", '', 10)
            for movement in cash_in:
                pdf.cell(100, 7, f"{movement['payment_ref']}", 1, 0, 'L')
                pdf.cell(90, 7, f"{format_currency(movement['amount'])}", 1, 1, 'R')
                
            # Total cash in
            pdf.set_font("Arial", 'B', 10)
            total_cash_in = sum(movement['amount'] for movement in cash_in)
            pdf.cell(100, 8, "Total ingresos:", 1, 0, 'R')
            pdf.cell(90, 8, f"{format_currency(total_cash_in)}", 1, 1, 'R')
        else:
            pdf.set_font("Arial", 'I', 10)
            pdf.cell(0, 8, "No hay ingresos registrados", 0, 1, 'C')
        
        # Cash out section with improved layout
        pdf.ln(5)
        pdf.set_font("Arial", 'B', 12)
        pdf.set_fill_color(245, 230, 230)  # Light red for cash out
        pdf.cell(0, 10, "RETIRADAS DE EFECTIVO", 1, 1, 'C', True)
        
        if cash_out:
            pdf.set_font("Arial", 'B', 10)
            # Table header
            pdf.cell(100, 8, "Concepto", 1, 0, 'C')
            pdf.cell(90, 8, "Monto", 1, 1, 'C')
            
            # Table rows
            pdf.set_font("Arial", '', 10)
            for movement in cash_out:
                pdf.cell(100, 7, f"{movement['payment_ref']}", 1, 0, 'L')
                pdf.cell(90, 7, f"{format_currency(abs(movement['amount']))}", 1, 1, 'R')
                
            # Total cash out
            pdf.set_font("Arial", 'B', 10)
            total_cash_out = abs(sum(movement['amount'] for movement in cash_out))
            pdf.cell(100, 8, "Total retiradas:", 1, 0, 'R')
            pdf.cell(90, 8, f"{format_currency(total_cash_out)}", 1, 1, 'R')
        else:
            pdf.set_font("Arial", 'I', 10)
            pdf.cell(0, 8, "No hay retiradas registradas", 0, 1, 'C')
        
        pdf.ln(10)
        
        # Sales summary section with detailed payment methods
        pdf.set_fill_color(240, 240, 240)
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 10, "RESUMEN DE VENTAS", 1, 1, 'C', True)
        pdf.ln(2)
        
        # Total sales
        pdf.set_font("Arial", '', 10)
        pdf.cell(100, 8, "Total de ventas:", 1, 0, 'L')
        pdf.cell(90, 8, f"{format_currency(session_data['total_payments_amount'])}", 1, 1, 'R')
        
        # Add payment method breakdown header
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(0, 8, "Desglose por método de pago:", 0, 1, 'L')
        
        # List all payment methods including cash
        pdf.set_font("Arial", '', 10)
        for method_name, method_amount in sorted_methods:
            if method_amount > 0:  # Only show methods with positive amounts
                # No special highlighting for cash row
                pdf.cell(100, 8, f"   {method_name}:", 1, 0, 'L')
                pdf.cell(90, 8, f"{format_currency(method_amount)}", 1, 1, 'R')
        
        # Add sales details
        sales_details = get_sales_details(session_id=session_data['id'])
        if sales_details:
            # Separate regular sales and refunds
            regular_sales = [order for order in sales_details if not order['is_refund']]
            refunds = [order for order in sales_details if order['is_refund']]
            
            pdf.add_page()
            pdf.set_font("Arial", 'B', 14)
            pdf.cell(0, 10, txt="DETALLE DE VENTAS", ln=True, align='C')
            pdf.ln(5)
            
            # Regular sales first
            if regular_sales:
                pdf.set_font("Arial", 'B', 12)
                pdf.set_fill_color(230, 245, 230)  # Light green for sales
                pdf.cell(0, 10, "VENTAS REGULARES", 1, 1, 'C', True)
                pdf.ln(2)
                
                for order in regular_sales:
                    pdf.set_font("Arial", 'B', 11)
                    pdf.cell(0, 10, txt=f"Orden: {order['order_name']} - {order['order_date']} - Total: {format_currency(order['order_amount'])}", ln=True)
                    
                    # Show payment methods
                    pdf.set_font("Arial", '', 10)
                    pdf.cell(200, 8, txt="Métodos de pago:", ln=True)
                    for payment in order['payments']:
                        if payment.get('is_cash', False) and payment.get('change', 0) > 0:
                            # Display detailed cash payment with change
                            pdf.cell(200, 6, txt=f"   {payment['method']}: {format_currency(payment['amount'])} (Entregó: {format_currency(payment['paid'])} - Cambio: {format_currency(payment['change'])})", ln=True)
                        else:
                            # Display normal payment
                            pdf.cell(200, 6, txt=f"   {payment['method']}: {format_currency(payment['amount'])}", ln=True)
                    
                    # Define table columns for order lines
                    pdf.set_font("Arial", 'B', 10)
                    col_width = [100, 30, 30, 30]
                    pdf.cell(col_width[0], 8, "Producto", 1, 0, 'C')
                    pdf.cell(col_width[1], 8, "Cant.", 1, 0, 'C')
                    pdf.cell(col_width[2], 8, "Precio", 1, 0, 'R')
                    pdf.cell(col_width[3], 8, "Subtotal", 1, 1, 'R')
                    
                    # Add data rows
                    pdf.set_font("Arial", '', 9)
                    for line in order['lines']:
                        product_name = line['product_id'][1]
                        if len(product_name) > 50:
                            product_name = product_name[:47] + "..."
                        
                        # Format integers instead of showing decimals
                        qty = int(line['qty']) if line['qty'] == int(line['qty']) else line['qty']
                        
                        pdf.cell(col_width[0], 7, product_name, 1, 0)
                        pdf.cell(col_width[1], 7, f"{qty}", 1, 0, 'C')
                        pdf.cell(col_width[2], 7, format_currency(line['price_unit']), 1, 0, 'R')
                        pdf.cell(col_width[3], 7, format_currency(line['price_subtotal']), 1, 1, 'R')
                    
                    pdf.ln(5)
            
            # Then refunds with different styling
            if refunds:
                pdf.set_font("Arial", 'B', 12)
                pdf.set_fill_color(255, 200, 200)  # Light red for refunds
                pdf.cell(0, 10, "REEMBOLSOS", 1, 1, 'C', True)
                pdf.ln(2)
                
                for order in refunds:
                    pdf.set_font("Arial", 'B', 11)
                    pdf.set_fill_color(255, 230, 230)  # Lighter red background for refund orders
                    pdf.cell(0, 10, f"Orden: {order['order_name']} - {order['order_date']} - Total: {format_currency(order['order_amount'])}", 1, 1, 'L', True)
                    
                    # Show payment methods
                    pdf.set_font("Arial", '', 10)
                    pdf.cell(200, 8, "Métodos de pago:", 0, 1, 'L')
                    for payment in order['payments']:
                        if payment.get('is_cash', False) and payment.get('change', 0) > 0:
                            # Display detailed cash payment with change
                            pdf.cell(200, 6, f"   {payment['method']}: {format_currency(payment['amount'])} (Entregó: {format_currency(payment['paid'])} - Cambio: {format_currency(payment['change'])})", 0, 1, 'L')
                        else:
                            # Display normal payment
                            pdf.cell(200, 6, f"   {payment['method']}: {format_currency(payment['amount'])}", 0, 1, 'L')
                    
                    # Define table columns for order lines
                    pdf.set_font("Arial", 'B', 10)
                    col_width = [100, 30, 30, 30]
                    pdf.cell(col_width[0], 8, "Producto", 1, 0, 'C')
                    pdf.cell(col_width[1], 8, "Cant.", 1, 0, 'C')
                    pdf.cell(col_width[2], 8, "Precio", 1, 0, 'R')
                    pdf.cell(col_width[3], 8, "Subtotal", 1, 1, 'R')
                    
                    # Add data rows
                    pdf.set_font("Arial", '', 9)
                    for line in order['lines']:
                        product_name = line['product_id'][1]
                        if len(product_name) > 50:
                            product_name = product_name[:47] + "..."
                        
                        # Format integers instead of showing decimals
                        qty = int(line['qty']) if line['qty'] == int(line['qty']) else line['qty']
                        
                        pdf.cell(col_width[0], 7, product_name, 1, 0)
                        pdf.cell(col_width[1], 7, f"{qty}", 1, 0, 'C')
                        pdf.cell(col_width[2], 7, format_currency(line['price_unit']), 1, 0, 'R')
                        pdf.cell(col_width[3], 7, format_currency(line['price_subtotal']), 1, 1, 'R')
                    
                    pdf.ln(5)

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