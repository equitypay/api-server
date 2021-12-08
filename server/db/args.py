from webargs import fields, validate

page_args = {
    "page": fields.Int(missing=1, validate=validate.Range(min=1))
}

broadcast_args = {
    "raw": fields.Str(required=True)
}

height_args = {
    "start": fields.Int(missing=None, validate=validate.Range(min=1)),
    "finish": fields.Int(missing=None, validate=validate.Range(min=1))
}
