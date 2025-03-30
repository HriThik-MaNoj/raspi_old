from flask import Flask, redirect

app = Flask(__name__)

@app.route('/verify/tx/<tx_hash>')
def old_route(tx_hash):
    print(f'Old route called with {tx_hash}')
    return redirect(f'/api/verify/tx/{tx_hash}')

@app.route('/api/verify/tx/<tx_hash>')
def new_route(tx_hash):
    print(f'New route called with {tx_hash}')
    return 'Success'

if __name__ == '__main__':
    print('Testing redirect...')
    client = app.test_client()
    response = client.get('/verify/tx/test123')
    print(f'Response status: {response.status_code}')
    print(f'Response location: {response.headers.get("Location")}')
    
    # Follow the redirect
    if response.status_code == 302:
        print('Following redirect...')
        redirect_response = client.get(response.headers.get("Location"))
        print(f'Redirect response status: {redirect_response.status_code}')
        print(f'Redirect response data: {redirect_response.data}')
