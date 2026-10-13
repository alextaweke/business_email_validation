import logging
import uuid
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from drf_spectacular.utils import extend_schema, OpenApiResponse
from .serializers import EmailValidationRequestSerializer
from .services.engine import validate_email_address

logger = logging.getLogger("validator")

class EmailValidateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=EmailValidationRequestSerializer,
        responses={200: OpenApiResponse(description="Validation outcome: true, false, or not_known."),
                   400: OpenApiResponse(description="Invalid request body.")},
        description="Estimates deliverability; does not send email. Requires X-API-Key.",
    )
    def post(self, request):
        serializer = EmailValidationRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"detail": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data
        try:
            result = validate_email_address(data["email"], data["check_smtp"])
            return Response(result, status=status.HTTP_200_OK)
        except Exception:
            request_id = str(uuid.uuid4())
            logger.exception("Unexpected validation failure")
            return Response({
                "detail": "Validation service temporarily failed.",
                "request_id": request_id,
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    return Response({"status": "ok"})
