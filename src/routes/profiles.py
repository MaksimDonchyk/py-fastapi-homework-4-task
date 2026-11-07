from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status, Form, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload

from database import get_db
from database.models.accounts import UserModel, UserProfileModel, UserGroupEnum
from schemas.profiles import ProfileCreateSchema, ProfileResponseSchema
from storages import S3StorageInterface
from config.dependencies import (
    get_s3_storage_client,
    get_jwt_auth_manager,
)
from security.interfaces import JWTAuthManagerInterface
from security.http import get_token

router = APIRouter(prefix="/users", tags=["Profiles"])


@router.post(
    "/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=status.HTTP_201_CREATED
)
async def create_user_profile(
        user_id: int,
        first_name: str = Form(...),
        last_name: str = Form(...),
        gender: str = Form(...),
        date_of_birth: date = Form(...),
        info: str = Form(...),
        avatar: UploadFile = File(...),
        token: str = Depends(get_token),
        db: AsyncSession = Depends(get_db),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
        s3_client: S3StorageInterface = Depends(get_s3_storage_client)
):
    try:
        payload = jwt_manager.decode_access_token(token)
        token_user_id = payload.get("sub") or payload.get("user_id")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired."
        )

    avatar_bytes = await avatar.read()

    try:
        profile_data = ProfileCreateSchema(
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            date_of_birth=date_of_birth,
            info=info,
            avatar=avatar_bytes
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )

    result = await db.execute(
        select(UserModel)
        .options(joinedload(UserModel.group))
        .where(UserModel.id == user_id)
    )
    user = result.scalars().first()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active."
        )

    admin_result = await db.execute(
        select(UserModel)
        .options(joinedload(UserModel.group))
        .where(UserModel.id == token_user_id)
    )
    requesting_user = admin_result.scalars().first()

    is_admin = requesting_user and requesting_user.group and requesting_user.group.name == UserGroupEnum.ADMIN
    if token_user_id is None or (str(token_user_id) != str(user_id) and not is_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile."
        )

    profile_result = await db.execute(
        select(UserProfileModel).where(UserProfileModel.user_id == user_id)
    )
    if profile_result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile."
        )

    avatar_filename = f"avatars/{user_id}_avatar.jpg"
    try:

        await s3_client.upload_file(
            file_data=profile_data.avatar,
            file_name=avatar_filename
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later."
        )

    new_profile = UserProfileModel(
        user_id=user_id,
        first_name=profile_data.first_name,
        last_name=profile_data.last_name,
        gender=profile_data.gender,
        date_of_birth=profile_data.date_of_birth,
        info=profile_data.info,
        avatar=avatar_filename
    )

    db.add(new_profile)
    await db.commit()
    await db.refresh(new_profile)

    return new_profile
