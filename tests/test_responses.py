from app.core.responses import ApiResponse


def test_success_response():
    response = ApiResponse(success=True, data={"hello": "world"})

    assert response.success is True
    assert response.error is None
    assert response.data == {"hello": "world"}