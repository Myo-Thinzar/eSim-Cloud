import django_filters
from django_filters import rest_framework as filters
from .serializers import StateSaveSerializer, SaveListSerializer
from .serializers import Base64ImageField
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.parsers import FormParser, JSONParser
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.generics import ListAPIView
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema
from .models import StateSave
from workflowAPI.models import Permission
from publishAPI.models import Project
from rest_framework import viewsets
import uuid
from django.contrib.auth import get_user_model
import logging
import traceback
import json
logger = logging.getLogger(__name__)


class StateSaveView(APIView):
    '''
    API to save the state of project to db which can be loaded or shared later
    Note: this is different from SnapshotSave which stores images
    THIS WILL ESCAPE DOUBLE QUOTES
    '''

    # Permissions should be validated here
    permission_classes = (IsAuthenticated,)
    # parser_classes = (FormParser,)

    @swagger_auto_schema(request_body=StateSaveSerializer)
    def post(self, request, *args, **kwargs):
        logger.info('Got POST for state save ')
        esim_libraries = json.loads(request.data.get('esim_libraries'))
        try:
            queryset = StateSave.objects.get(
                data_dump=request.data["data_dump"], branch=request.data["branch"])
            serializer = StateSaveSerializer(data=request.data)
            if serializer.is_valid():
                queryset.name = serializer.data["name"]
                queryset.description = serializer.data["description"]
                queryset.save()
                response = serializer.data
                response['duplicate'] = True
                return Response(response)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except StateSave.DoesNotExist:
            img = Base64ImageField(max_length=None, use_url=True)
            filename, content = img.update(request.data['base64_image'])
            try:
                project = Project.objects.get(
                    project_id=request.data.get('project_id'))
                state_save = StateSave(
                    data_dump=request.data.get('data_dump'),
                    description=request.data.get('description'),
                    name=request.data.get('name'),
                    owner=request.user,
                    branch=request.data.get('branch'),
                    version=request.data.get('version'),
                    project=project.project_id
                )
            except Project.DoesNotExist:
                state_save = StateSave(
                    data_dump=request.data.get('data_dump'),
                    description=request.data.get('description'),
                    name=request.data.get('name'),
                    owner=request.user,
                    branch=request.data.get('branch'),
                    version=request.data.get('version')
                )
            if request.data.get('save_id'):
                state_save.save_id = request.data.get('save_id')
            state_save.base64_image.save(filename, content)
            print(state_save)
            state_save.esim_libraries.set(esim_libraries)
            try:
                state_save.save()
                return Response(StateSaveSerializer(state_save).data)
            except Exception:
                return Response(status=status.HTTP_400_BAD_REQUEST)


class CopyStateView(APIView):
    permission_classes = (IsAuthenticated,)
    parser_classes = (FormParser, JSONParser)

    def post(self, request, save_id):
        if isinstance(save_id, uuid.UUID):
            # Check for permissions and sharing settings here
            try:
                saved_state = StateSave.objects.get(save_id=save_id)
            except StateSave.DoesNotExist:
                return Response({'error': 'Does not Exist'},
                                status=status.HTTP_404_NOT_FOUND)
            saved_state.save_id = None
            saved_state.project = None
            saved_state.name = "Copy of " + saved_state.name
            saved_state.owner = self.request.user
            saved_state.save()
            return Response({"save_id": saved_state.save_id})


class StateFetchUpdateView(APIView):
    """
    Returns Saved data for given save id ,
    Only user who saved the state can access / update it
    THIS WILL ESCAPE DOUBLE QUOTES

    """
    permission_classes = (AllowAny,)
    parser_classes = (FormParser, JSONParser)
    methods = ['GET']

    @swagger_auto_schema(responses={200: StateSaveSerializer})
    def get(self, request, save_id, version, branch):

        if isinstance(save_id, uuid.UUID):
            # Check for permissions and sharing settings here
            try:
                saved_state = StateSave.objects.get(
                    save_id=save_id, version=version, branch=branch)
            except StateSave.DoesNotExist:
                return Response({'error': 'Does not Exist'},
                                status=status.HTTP_404_NOT_FOUND)
            # Verifies owner
            if self.request.user != saved_state.owner and not saved_state.shared:  # noqa
                return Response({'error': 'not the owner and not shared'},
                                status=status.HTTP_401_UNAUTHORIZED)
            try:
                serialized = StateSaveSerializer(
                    saved_state, context={'request': request})
                User = get_user_model()
                owner_name = User.objects.get(
                    id=serialized.data.get('owner'))
                data = {}
                data.update(serialized.data)
                data['owner'] = owner_name.username
                return Response(data)
            except Exception:
                traceback.print_exc()
                return Response({'error': 'Not Able To Serialize'},
                                status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({'error': 'Invalid sharing state'},
                            status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(responses={200: StateSaveSerializer})
    def post(self, request, save_id):
        if isinstance(save_id, uuid.UUID):
            # Check for permissions and sharing settings here
            try:
                saved_state = StateSave.objects.get(save_id=save_id)
            except StateSave.DoesNotExist:
                return Response({'error': 'Does not Exist'},
                                status=status.HTTP_404_NOT_FOUND)

            # Verifies owner
            if self.request.user != saved_state.owner:  # noqa
                return Response({'error': 'not the owner and not shared'},
                                status=status.HTTP_401_UNAUTHORIZED)

            if not request.data['data_dump'] and not request.data['shared']:
                return Response({'error': 'not a valid PUT request'},
                                status=status.HTTP_406_NOT_ACCEPTABLE)

            try:
                # if data dump, shared,name and description needs to be updated
                if 'data_dump' in request.data:
                    saved_state.data_dump = request.data['data_dump']
                if 'shared' in request.data:
                    saved_state.shared = bool(request.data['shared'])
                if 'name' in request.data:
                    saved_state.name = request.data['name']
                if 'description' in request.data:
                    saved_state.description = request.data['description']
                # if thumbnail needs to be updated
                if 'base64_image' in request.data:
                    img = Base64ImageField(max_length=None, use_url=True)
                    filename, content = img.update(
                        request.data['base64_image'])
                    saved_state.base64_image.save(filename, content)
                if 'esim_libraries' in request.data:
                    esim_libraries = json.loads(
                        request.data.get('esim_libraries'))
                    saved_state.esim_libraries.set(esim_libraries)
                saved_state.save()
                serialized = SaveListSerializer(saved_state)
                return Response(serialized.data)
            except Exception:
                return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            return Response({'error': 'Invalid sharing state'},
                            status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(responses={200: StateSaveSerializer})
    def delete(self, request, save_id, version, branch):
        if isinstance(save_id, uuid.UUID):
            try:
                saved_state = StateSave.objects.get(
                    save_id=save_id, version=version, branch=branch)
            except StateSave.DoesNotExist:
                return Response({'error': 'Does not Exist'},
                                status=status.HTTP_404_NOT_FOUND)
            # Verifies owner
            if saved_state.owner == self.request.user and (saved_state.project is None or Permission.objects.filter(role__in=self.request.user.groups.all(), del_own_states=saved_state.project.state).exists()):
                pass
            else:
                return Response(status=status.HTTP_401_UNAUTHORIZED)
            if saved_state.project is not None:
                saved_state.project.delete()
            saved_state.delete()
            return Response({'done': True})
        else:
            return Response({'error': 'Invalid sharing state'},
                            status=status.HTTP_400_BAD_REQUEST)


class StateShareView(APIView):
    """
    Enables sharing for the given saved state
    Note: Only authorized user can do this

    """
    permission_classes = (AllowAny,)
    methods = ['GET']

    @swagger_auto_schema(responses={200: StateSaveSerializer})
    def post(self, request, save_id, sharing, version, branch):

        if isinstance(save_id, uuid.UUID):
            # Check for permissions and sharing settings here
            try:
                saved_state = StateSave.objects.get(
                    save_id=save_id, version=version, branch=branch)
            except StateSave.DoesNotExist:
                return Response({'error': 'Does not Exist'},
                                status=status.HTTP_404_NOT_FOUND)

            # Verifies owner
            if self.request.user != saved_state.owner:  # noqa
                return Response({'error': 'Not the owner'},
                                status=status.HTTP_401_UNAUTHORIZED)
            try:
                if sharing == 'on':
                    saved_state.shared = True
                elif sharing == 'off':
                    saved_state.shared = False
                else:
                    return Response({'error': 'Invalid sharing state'},
                                    status=status.HTTP_400_BAD_REQUEST)
                saved_state.save()
                serialized = StateSaveSerializer(saved_state)
                return Response(serialized.data)
            except Exception:
                return Response(serialized.error)
        else:
            return Response({'error': 'Invalid sharing state'},
                            status=status.HTTP_400_BAD_REQUEST)


class UserSavesView(APIView):
    """
    Returns Saved data for given username,
    Only user who saved the state can access it
    THIS WILL ESCAPE DOUBLE QUOTES

    """
    permission_classes = (IsAuthenticated,)
    parser_classes = (FormParser, JSONParser)
    methods = ['GET']

    @swagger_auto_schema(responses={200: StateSaveSerializer})
    def get(self, request):
        saved_state = StateSave.objects.filter(owner=self.request.user).order_by(
            "save_id", "-save_time").distinct("save_id")
        try:
            serialized = StateSaveSerializer(saved_state, many=True)
            return Response(serialized.data)
        except Exception:
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ArduinoSaveList(APIView):
    """
    List of Arduino Projects
    """
    permission_classes = (IsAuthenticated,)
    parser_classes = (FormParser, JSONParser)
    methods = ['GET']

    @swagger_auto_schema(responses={200: StateSaveSerializer})
    def get(self, request):
        saved_state = StateSave.objects.filter(
            owner=self.request.user, is_arduino=True).order_by('-save_time')
        try:
            serialized = SaveListSerializer(
                saved_state, many=True, context={'request': request})
            return Response(serialized.data)
        except Exception:
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SaveSearchFilterSet(django_filters.FilterSet):
    class Meta:
        model = StateSave
        fields = {
            'name': ['icontains'],
            'description': ['icontains'],
            'save_time': ['icontains'],
            'create_time': ['icontains'],
            'is_arduino': ['exact']
        }


class SaveSearchViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Search Project
    """

    def get_queryset(self):
        queryset = StateSave.objects.filter(
            owner=self.request.user).order_by('-save_time')
        return queryset
    serializer_class = SaveListSerializer
    filter_backends = (filters.DjangoFilterBackend,)
    filterset_class = SaveSearchFilterSet


class StateSaveAllVersions(APIView):
    serializer_class = SaveListSerializer
    permission_classes = (IsAuthenticated,)

    @swagger_auto_schema(responses={200: SaveListSerializer})
    def get(self, request, save_id):
        queryset = StateSave.objects.filter(
            owner=self.request.user, save_id=save_id)
        try:
            serialized = SaveListSerializer(
                queryset, many=True, context={'request': request})
            return Response(serialized.data)
        except Exception:
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GetStateSpecificVersion(APIView):
    serializer_class = StateSaveSerializer
    permission_classes = (IsAuthenticated,)

    @swagger_auto_schema(responses={200: StateSaveSerializer})
    def get(self, request, save_id, version, branch):
        queryset = StateSave.objects.get(
            save_id=save_id, version=version, owner=self.request.user, branch=branch)
        try:
            serialized = StateSaveSerializer(
                queryset)
            return Response(serialized.data)
        except Exception:
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)
