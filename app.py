from flask import Flask, request, render_template, redirect, url_for, session
import mysql.connector
import bcrypt
import mercadopago

app = Flask(__name__)
app.secret_key = 'sua_chave_secreta_aqui'

# Credenciais do Mercado Pago
MERCADO_PAGO_ACCESS_TOKEN = "APP_USR-2957403152017240-091400-a4ac3b9b1025c4dce0447d24868e088e-657641042"

# Configuração da API do Mercado Pago
sdk = mercadopago.SDK(MERCADO_PAGO_ACCESS_TOKEN)

# Configurações do banco de dados MySQL
DATABASE_CONFIG = {
    'user': 'root',
    'password': 'braga152',
    'host': 'localhost',
    'database': 'meu_banco',
}

def get_db_connection():
    return mysql.connector.connect(**DATABASE_CONFIG)

def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def check_password(stored_hash, password):
    return bcrypt.checkpw(password.encode(), stored_hash.encode())

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('user_balance'))
    
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form['full_name']
        age = request.form['age']
        phone = request.form['phone']
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute('SELECT * FROM users WHERE username = %s', (username,))
        user = cur.fetchone()

        if user:
            cur.close()
            conn.close()
            return 'Usuário já existe', 400

        hashed_password = hash_password(password)

        cur.execute('''
            INSERT INTO users (username, password_hash, full_name, age, phone, balance)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (username, hashed_password, full_name, age, phone, 0.00))

        conn.commit()
        cur.close()
        conn.close()

        return redirect(url_for('index'))

    return render_template('register.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute('SELECT id, password_hash FROM users WHERE username = %s', (username,))
    user = cur.fetchone()
    cur.close()
    conn.close()

    if user and check_password(user['password_hash'], password):
        session['user_id'] = user['id']
        return redirect(url_for('user_balance'))
    return 'Usuário ou senha incorretos', 401

@app.route('/user/balance', methods=['GET', 'POST'])
def user_balance():
    if 'user_id' not in session:
        return redirect(url_for('index'))

    user_id = session['user_id']
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute('SELECT balance, full_name, age, phone FROM users WHERE id = %s', (user_id,))
    user_data = cur.fetchone()
    cur.close()
    conn.close()

    if request.method == 'POST':
        if 'withdraw' in request.form:
            withdrawal_amount = float(request.form['withdrawal_amount'])
            if withdrawal_amount <= user_data['balance']:
                # Deduzir o valor do saldo
                new_balance = user_data['balance'] - withdrawal_amount
                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute('UPDATE users SET balance = %s WHERE id = %s', (new_balance, user_id))
                conn.commit()
                cur.close()
                conn.close()

                # Processar o pagamento via Pix
                preference_data = {
                    'items': [{
                        'title': 'Saque via Pix',
                        'quantity': 1,
                        'unit_price': withdrawal_amount,
                        'currency_id': 'BRL',
                    }],
                    'payment_methods': {
                        'excluded_payment_types': [{'id': 'ticket'}]
                    },
                    'back_urls': {
                        'success': url_for('withdraw_success', _external=True),
                        'failure': url_for('withdraw_failure', _external=True),
                        'pending': url_for('withdraw_pending', _external=True),
                    },
                    'auto_return': 'approved',
                }

                preference_response = sdk.preference().create(preference_data)
                preference_id = preference_response['response']['id']
                return redirect(preference_response['response']['init_point'])
            else:
                return 'Saldo insuficiente para saque', 400

    if user_data:
        return render_template('user_balance.html', user_data=user_data)

    return 'Dados do usuário não encontrados', 404

@app.route('/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))

@app.route('/payment/callback', methods=['POST'])
def payment_callback():
    data = request.json
    payment_id = data.get('id')
    status = data.get('status')

    # Processar o status do pagamento
    if status == 'approved':
        # Atualizar o saldo do usuário, registrar a transação, etc.
        pass
    elif status == 'rejected':
        # Lidar com pagamentos rejeitados
        pass

    return '', 200

@app.route('/withdraw/success')
def withdraw_success():
    return 'Saque realizado com sucesso!'

@app.route('/withdraw/failure')
def withdraw_failure():
    return 'Falha ao realizar saque.'

@app.route('/withdraw/pending')
def withdraw_pending():
    return 'Saque pendente. Verifique o status posteriormente.'

if __name__ == '__main__':
    app.run(debug=True)

