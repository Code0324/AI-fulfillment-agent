"""Local mock supplier checkout page for sandbox testing.

This module serves a local HTML page that simulates a supplier checkout form.
All data is synthetic — no real Amazon or supplier data is used.
"""

SANDBOX_CHECKOUT_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mock Supplier Checkout - SANDBOX</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f5f5; padding: 20px; }
        .banner { background: #fef3cd; border: 1px solid #ffc107; padding: 12px; border-radius: 8px; margin-bottom: 20px; text-align: center; font-weight: bold; color: #856404; }
        .container { max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); padding: 24px; }
        h1 { font-size: 20px; margin-bottom: 20px; color: #333; }
        .form-group { margin-bottom: 16px; }
        label { display: block; font-size: 14px; font-weight: 500; margin-bottom: 4px; color: #555; }
        input, select { width: 100%; padding: 10px 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; }
        input:focus, select:focus { outline: none; border-color: #4a90d9; box-shadow: 0 0 0 2px rgba(74,144,217,0.2); }
        .row { display: flex; gap: 16px; }
        .row .form-group { flex: 1; }
        .submit-btn { width: 100%; padding: 12px; background: #4a90d9; color: white; border: none; border-radius: 6px; font-size: 16px; font-weight: 500; cursor: pointer; margin-top: 8px; }
        .submit-btn:hover { background: #357abd; }
        .result { margin-top: 16px; padding: 12px; background: #e8f5e9; border-radius: 6px; display: none; }
        .result.show { display: block; }
        .meta { font-size: 12px; color: #888; margin-top: 16px; text-align: center; }
    </style>
</head>
<body>
    <div class="banner">
        ⚠️ SANDBOX — NO AMAZON CONNECTION — TEST DATA ONLY
    </div>
    <div class="container">
        <h1>Mock Supplier Checkout</h1>
        <form id="checkout-form">
            <div class="row">
                <div class="form-group">
                    <label for="first_name">First Name *</label>
                    <input type="text" id="first_name" name="first_name" required>
                </div>
                <div class="form-group">
                    <label for="last_name">Last Name *</label>
                    <input type="text" id="last_name" name="last_name" required>
                </div>
            </div>
            <div class="form-group">
                <label for="address1">Address 1 *</label>
                <input type="text" id="address1" name="address1" required>
            </div>
            <div class="form-group">
                <label for="address2">Address 2</label>
                <input type="text" id="address2" name="address2">
            </div>
            <div class="row">
                <div class="form-group">
                    <label for="city">City *</label>
                    <input type="text" id="city" name="city" required>
                </div>
                <div class="form-group">
                    <label for="state">State *</label>
                    <input type="text" id="state" name="state" required>
                </div>
            </div>
            <div class="row">
                <div class="form-group">
                    <label for="zip">ZIP Code *</label>
                    <input type="text" id="zip" name="zip" required>
                </div>
                <div class="form-group">
                    <label for="country">Country</label>
                    <select id="country" name="country">
                        <option value="US">United States</option>
                        <option value="CA">Canada</option>
                        <option value="UK">United Kingdom</option>
                    </select>
                </div>
            </div>
            <div class="form-group">
                <label for="phone">Phone</label>
                <input type="tel" id="phone" name="phone">
            </div>
            <div class="form-group">
                <label for="shipping_method">Shipping Method</label>
                <select id="shipping_method" name="shipping_method">
                    <option value="standard">Standard Shipping</option>
                    <option value="express">Express Shipping</option>
                    <option value="overnight">Overnight Shipping</option>
                </select>
            </div>
            <button type="submit" class="submit-btn">Place Order</button>
        </form>
        <div id="result" class="result"></div>
        <div class="meta">
            Environment: SANDBOX | No real orders are placed
        </div>
    </div>
    <script>
        document.getElementById('checkout-form').addEventListener('submit', function(e) {
            e.preventDefault();
            var formData = new FormData(this);
            var data = {};
            formData.forEach(function(value, key) { data[key] = value; });
            var result = document.getElementById('result');
            result.innerHTML = '<strong>Order Submitted (Mock)</strong><br>' +
                'Name: ' + data.first_name + ' ' + data.last_name + '<br>' +
                'Address: ' + data.address1 + '<br>' +
                'City: ' + data.city + ', ' + data.state + ' ' + data.zip + '<br>' +
                'Shipping: ' + data.shipping_method;
            result.className = 'result show';
        });
    </script>
</body>
</html>
"""


def get_sandbox_page_html() -> str:
    """Return the sandbox checkout page HTML."""
    return SANDBOX_CHECKOUT_HTML
