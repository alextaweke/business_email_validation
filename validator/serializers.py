from rest_framework import serializers


class EmailValidationRequestSerializer(serializers.Serializer):
    email = serializers.CharField(max_length=254, trim_whitespace=True)
    check_smtp = serializers.BooleanField(required=False, default=False)

    def validate_email(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("This field may not be blank.")
        return value
