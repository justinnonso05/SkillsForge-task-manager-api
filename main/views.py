from drf_spectacular.utils import extend_schema_view, extend_schema, OpenApiParameter, OpenApiExample
from rest_framework import generics
from rest_framework.views import APIView
from .models import Task
from .serializers import TaskSerializer
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import authenticate
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from django.db import IntegrityError
from .serializers import UserSerializer
from django.contrib.auth.models import User
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.parsers import MultiPartParser, FormParser
from django.db.models import Q


@extend_schema(
    summary="User Signup",
    description="Register a new user with username and password.",
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "username": {"type": "string"},
                "password": {"type": "string"},
            },
        }
    },
    responses={
        201: {"type": "object", "properties": {"message": {"type": "string"}}},
        400: {"type": "object", "properties": {"error": {"type": "string"}}},
    },
)
class UserSignupView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')

        if not username or not password:
            return Response({"error": "Username and password are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.create_user(username=username, password=password)
            return Response({
                'message': f"User {user.username} created successfully. Please log in to get your tokens."
            }, status=status.HTTP_201_CREATED)
        except IntegrityError as e:
            if 'auth_user.username' in str(e):
                return Response({"error": "A user with this username already exists."}, status=status.HTTP_400_BAD_REQUEST)
            return Response({"error": "An unknown error occurred."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    summary="User Login",
    description="Login an existing user and generate access and refresh tokens.",
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "username": {"type": "string"},
                "password": {"type": "string"},
            },
        }
    }, 
    responses={
        200: {
            "type": "object",
            "properties": {
                "token": {"type": "string"},
                "refresh": {"type": "string"},
                "user": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "username": {"type": "string"}
                    }
                }
            }
        },
        401: {"type": "object", "properties": {"error": {"type": "string"}}},
    },
)
class UserLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        
        user = authenticate(username=username, password=password)
        
        if user is not None:
            # Generate tokens only on login
            refresh = RefreshToken.for_user(user)
            return Response({
                'token': str(refresh.access_token),
                'refresh': str(refresh),
                'user': {
                    'id': user.id,
                    'username': user.username
                }
            })
        else:
            return Response({'error': 'Invalid credentials'}, 
                status=status.HTTP_401_UNAUTHORIZED)



@extend_schema(
    summary="List Tasks",
    description="Retrieve a list of all Tasks in the system.",
    parameters=[
        OpenApiParameter(name="category", type=str, description="Filter tasks by category", required=False),
        OpenApiParameter(name="search", type=str, description="Search for a task with a keyword", required=False)
    ],
    responses={200: TaskSerializer(many=True)},
)
class TaskList(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        tasks = Task.objects.filter(user=request.user)
        category_query = request.query_params.get('category', None)
        search_query = request.query_params.get('search', None)

        if search_query:
            tasks = tasks.filter(Q(title__icontains=search_query.upper()))
        if category_query:
            tasks = tasks.filter(category=category_query)

        serializer = TaskSerializer(tasks, many=True)
        return Response(serializer.data)


@extend_schema(
    summary="Create a Task",
    description="Create a new Task by providing necessary details.",
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "description": {"type": "string"},
                "category": {"type": "string"},
            },
        }
    },
    responses={201: TaskSerializer},
)
class TaskCreate(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk=None, format=None):
        serializer = TaskSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    summary="Retrieve a Task",
    description="Get details of a specific task by its ID.",
    responses={200: TaskSerializer},
)
class TaskRetrieve(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk=None):
        try:
            task = Task.objects.get(id=pk, user=request.user)
            serializer = TaskSerializer(task)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Task.DoesNotExist:
            return Response({"error": "Task not found or you do not have the required permissions to view the task."}, status=status.HTTP_404_NOT_FOUND)


@extend_schema(
    summary="Partially Update a Task",
    description="Update specific fields of a task without replacing the entire object.",
    request=TaskSerializer,
    responses={200: TaskSerializer},
)
class TaskUpdate(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk, format=None):
        try:
            task = Task.objects.get(pk=pk, user=request.user)
            serializer = TaskSerializer(task, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
        except Task.DoesNotExist:
            return Response({"error": "Task not found or you do not have the required permissions to view the task."}, status=status.HTTP_404_NOT_FOUND)


@extend_schema(
    summary="Delete a Task",
    description="Remove a specific task from the system permanently.",
    responses={204: None},
)
class TaskDelete(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk, format=None):
        try:
            task = Task.objects.get(pk=pk, user=request.user)
            task.delete()
            return Response({"message": "Task deleted successfully."}, status=status.HTTP_204_NO_CONTENT)
        except Task.DoesNotExist:
            return Response({"error": "Task not found or you do not have the required permissions to delete the task."}, status=status.HTTP_404_NOT_FOUND)
