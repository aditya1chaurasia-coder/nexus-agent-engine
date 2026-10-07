from app.sandbox import ExecutionSandbox

def test_sandbox_success():
    code = 'print(sum([x for x in range(10)]))'
    ret, out, err = ExecutionSandbox.run_python_code(code)
    assert ret == 0
    assert out == '45'
    assert err == ''

def test_sandbox_runtime_error():
    code = 'x = 1 / 0'
    ret, out, err = ExecutionSandbox.run_python_code(code)
    assert ret != 0
    assert 'ZeroDivisionError' in err
