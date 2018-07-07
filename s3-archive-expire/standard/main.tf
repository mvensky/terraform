provider "aws" {
    region = "us-west-2"
}

resource "aws_s3_bucket" "bucket" {
    bucket = "newterraformbucket"

    lifecycle_rule {
        id = "test_rule"
        enabled = true
        prefix = "layer-one/layer-two"

        transition {
            days = 30
            storage_class = "GLACIER"
        }

        expiration {
            days = 365
        }
    }
}
