"""Draws a synthetic picture of stones on the floor, as a camera would see it.

Each face is a flat picture warped into place (warpPerspective). A depth buffer keeps,
for every pixel, only the nearest surface, so stacked or touching boxes hide each other right.
Then the picture is degraded like a real one: light, blur, noise, lens distortion and JPEG.
"""

from dataclasses import dataclass, field

import cv2
import numpy as np

from vision.simulation.boxTexture import SceneBox, StoneTextures, buildBoxFaces
from vision.simulation.sceneCamera import SceneCamera, buildPixelRays, worldToCamera


@dataclass
class SceneOptions:
    """What the floor looks like and how the picture is degraded."""

    # Grey-green floor in BGR, with darker lines every lineSpacingMm
    floorColor: tuple[int, int, int] = (110, 125, 105)
    lineColor: tuple[int, int, int] = (80, 90, 75)
    lineSpacingMm: float = 500.0
    lineWidthMm: float = 12.0
    # Floor rectangles painted brown (xMin, yMin, xMax, yMax in mm): flat things that are not stones
    brownPatchesMm: list[tuple[float, float, float, float]] = field(default_factory=list)
    backgroundColor: tuple[int, int, int] = (200, 200, 205)
    # Everything is multiplied by this: 0.7 is a darker room, 1.3 a brighter one
    lightFactor: float = 1.0
    blurKernelPx: int = 0
    noiseSigma: float = 0.0
    # 0 keeps the perfect picture; 1 to 100 saves and reads it back as a JPEG of that quality
    jpegQuality: int = 0


def renderScene(camera: SceneCamera, boxes: list[SceneBox], textures: StoneTextures, options: SceneOptions,
                randomGenerator: np.random.Generator) -> np.ndarray:
    """Returns the BGR picture of the boxes on the floor seen from the camera."""
    raysCamera: np.ndarray = buildPixelRays(camera)
    image, depth = renderFloor(camera, raysCamera, options)
    textureByKind: dict[str, np.ndarray] = {
        "labelled": textures.labelledFace,
        "covered": textures.coveredFace,
        "end": textures.endFace,
    }
    for box in boxes:
        for corners, normal, kind in buildBoxFaces(box):
            drawFace(image, depth, camera, raysCamera, (corners, normal, textureByKind[kind]))
    return degradePicture(image, camera, options, randomGenerator)


def renderFloor(camera: SceneCamera, raysCamera: np.ndarray, options: SceneOptions) -> tuple[np.ndarray, np.ndarray]:
    """Floor where the ray goes down, background elsewhere. Returns the picture and the depth of each pixel."""
    heightPx, widthPx = raysCamera.shape[:2]
    # Ray of each pixel in the world: origin = camera position, direction = rotation transposed x ray
    raysWorld: np.ndarray = raysCamera @ camera.rotation
    downward: np.ndarray = raysWorld[:, :, 2] < -1e-9
    # Distance along the ray (in units of the camera z, so it is also the depth) to the plane z = 0
    hitDepth: np.ndarray = np.where(downward, -camera.positionMm[2] / np.where(downward, raysWorld[:, :, 2], -1.0), np.inf)
    # Rays that never reach the floor get distance 0 here, only to avoid infinity times zero
    finiteDepth: np.ndarray = np.where(downward, hitDepth, 0.0)
    floorX: np.ndarray = camera.positionMm[0] + finiteDepth * raysWorld[:, :, 0]
    floorY: np.ndarray = camera.positionMm[1] + finiteDepth * raysWorld[:, :, 1]
    image: np.ndarray = np.empty((heightPx, widthPx, 3), dtype=np.float64)
    image[:] = options.backgroundColor
    image[downward] = options.floorColor
    halfLine: float = options.lineWidthMm / 2
    onLineX: np.ndarray = np.abs(np.mod(floorX + halfLine, options.lineSpacingMm) - halfLine) < halfLine
    onLineY: np.ndarray = np.abs(np.mod(floorY + halfLine, options.lineSpacingMm) - halfLine) < halfLine
    image[downward & (onLineX | onLineY)] = options.lineColor
    for xMin, yMin, xMax, yMax in options.brownPatchesMm:
        insidePatch: np.ndarray = downward & (floorX >= xMin) & (floorX <= xMax) & (floorY >= yMin) & (floorY <= yMax)
        image[insidePatch] = (100, 145, 188)
    return image, np.where(downward, hitDepth, np.inf)


def drawFace(image: np.ndarray, depth: np.ndarray, camera: SceneCamera, raysCamera: np.ndarray,
             face: tuple[np.ndarray, np.ndarray, np.ndarray]) -> None:
    """Warps one face picture into the image where it is nearer than what is already drawn."""
    corners, normal, texture = face
    cornersCamera: np.ndarray = worldToCamera(camera, corners)
    # Back faces look away from the camera; a face crossing the camera plane is skipped
    isFacingCamera: bool = float(np.dot(normal, camera.positionMm - corners.mean(axis=0))) > 0.0
    if not isFacingCamera or cornersCamera[:, 2].min() < 1.0:
        return
    cornersPx: np.ndarray = (cornersCamera @ camera.cameraMatrix.T)[:, :2] / cornersCamera[:, 2:3]
    textureHeight, textureWidth = texture.shape[:2]
    textureCorners: np.ndarray = np.array(
        [[0, 0], [textureWidth - 1, 0], [textureWidth - 1, textureHeight - 1], [0, textureHeight - 1]], dtype=np.float32)
    homography: np.ndarray = cv2.getPerspectiveTransform(textureCorners, cornersPx.astype(np.float32))
    imageSize: tuple[int, int] = (camera.widthPx, camera.heightPx)
    warped: np.ndarray = cv2.warpPerspective(texture, homography, imageSize, flags=cv2.INTER_LINEAR)
    mask: np.ndarray = cv2.warpPerspective(np.full((textureHeight, textureWidth), 255, np.uint8), homography,
                                           imageSize, flags=cv2.INTER_NEAREST) > 0
    # Depth of the face plane on each pixel: n.(t x ray) = n.p0, solved for t
    normalCamera: np.ndarray = camera.rotation @ normal
    planeOffset: float = float(np.dot(normalCamera, cornersCamera[0]))
    denominator: np.ndarray = raysCamera @ normalCamera
    faceDepth: np.ndarray = np.where(np.abs(denominator) > 1e-9, planeOffset / np.where(denominator == 0, 1.0, denominator),
                                     np.inf)
    isNearer: np.ndarray = mask & (faceDepth > 0) & (faceDepth < depth)
    # Light from above and a bit from the front: top faces brighter than the sides
    lightDirection: np.ndarray = np.array([-0.3, 0.2, 0.93])
    shade: float = 0.7 + 0.3 * max(0.0, float(np.dot(normal, lightDirection)))
    image[isNearer] = warped[isNearer] * shade
    depth[isNearer] = faceDepth[isNearer]


def degradePicture(image: np.ndarray, camera: SceneCamera, options: SceneOptions,
                   randomGenerator: np.random.Generator) -> np.ndarray:
    """Light, lens distortion, blur, noise and JPEG, in the order a real camera adds them."""
    picture: np.ndarray = np.clip(image * options.lightFactor, 0, 255).astype(np.uint8)
    if np.any(camera.distCoeffs != 0):
        picture = applyLensDistortion(picture, camera)
    if options.blurKernelPx > 1:
        kernelPx: int = options.blurKernelPx | 1
        picture = cv2.GaussianBlur(picture, (kernelPx, kernelPx), 0)
    if options.noiseSigma > 0:
        noise: np.ndarray = randomGenerator.normal(0.0, options.noiseSigma, picture.shape)
        picture = np.clip(picture + noise, 0, 255).astype(np.uint8)
    if options.jpegQuality > 0:
        _, encoded = cv2.imencode(".jpg", picture, [cv2.IMWRITE_JPEG_QUALITY, options.jpegQuality])
        decoded = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
        picture = picture if decoded is None else decoded
    return picture


def applyLensDistortion(picture: np.ndarray, camera: SceneCamera) -> np.ndarray:
    """Bends a perfect picture as the lens would: each output pixel takes its undistorted source."""
    columns, rows = np.meshgrid(np.arange(camera.widthPx, dtype=np.float32), np.arange(camera.heightPx, dtype=np.float32))
    distortedPixels: np.ndarray = np.stack([columns, rows], axis=-1).reshape(-1, 1, 2)
    sourcePixels: np.ndarray = cv2.undistortPoints(distortedPixels, camera.cameraMatrix, camera.distCoeffs,
                                                   P=camera.cameraMatrix)
    mapX: np.ndarray = sourcePixels[:, 0, 0].reshape(camera.heightPx, camera.widthPx).astype(np.float32)
    mapY: np.ndarray = sourcePixels[:, 0, 1].reshape(camera.heightPx, camera.widthPx).astype(np.float32)
    return cv2.remap(picture, mapX, mapY, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
