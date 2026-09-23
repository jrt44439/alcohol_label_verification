def test_list_products_empty(client):
    response = client.get("/products/")
    assert response.status_code == 200
    assert b"No products saved yet" in response.data


def test_create_product(client):
    response = client.post(
        "/products/new",
        data={
            "name": "Old Ridge Bourbon",
            "brand_name": "Old Ridge",
            "class_type": "Bourbon Whiskey",
            "alcohol_content": "45% ALC/VOL (90 PROOF)",
            "net_contents": "750 mL",
            "producer_info": "Old Ridge Distillery, Frankfort, KY",
            "country_of_origin": "",
            "action": "save",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Old Ridge Bourbon" in response.data


def test_extract_action_without_file_flashes_error(client):
    response = client.post("/products/new", data={"name": "Old Ridge Bourbon", "action": "extract"})
    assert response.status_code == 200
    assert b"Choose a PDF or Word document" in response.data


def test_create_product_requires_name(client):
    response = client.post("/products/new", data={"name": ""})
    assert response.status_code == 200
    assert b"Product name is required" in response.data


def test_edit_product(client):
    client.post("/products/new", data={"name": "Test Product"})
    from app.models import product as product_model

    with client.application.app_context():
        products = product_model.get_all()
    product_id = products[0].id

    response = client.post(
        f"/products/{product_id}/edit",
        data={"name": "Renamed Product"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Renamed Product" in response.data


def test_delete_product(client):
    client.post("/products/new", data={"name": "Delete Me"})
    from app.models import product as product_model

    with client.application.app_context():
        products = product_model.get_all()
    product_id = products[0].id

    response = client.post(f"/products/{product_id}/delete", follow_redirects=True)
    assert response.status_code == 200
    assert b"No products saved yet" in response.data

    with client.application.app_context():
        assert product_model.get_by_id(product_id) is None
