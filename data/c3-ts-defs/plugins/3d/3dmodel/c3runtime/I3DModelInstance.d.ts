
type Model3DRenderModeType = "hierarchy" | "isolate";
type Model3DTransformTypes = "offset" | "rotation" | "scale";
type Model3DResetTransformTypes = "offset" | "rotation" | "scale" | "all";
type Model3DAxisScaleModeTypes = "legacy" | "fit" | "stretch";
type Model3DNodeTypes = "mesh" | "bone";
type Model3DTransformLayers = "output" | "animation" | "programmatic";
type Model3DCullingModes = "none" | "back" | "front" | "model";
type Model3DAnimationModeTypes = "average" | "mask";

type Model3DLoadUrlTargets = "object-type" | "instance";

type Model3DVec3 = {
	x: number;
	y: number;
	z: number;
};

type Model3DQuaternion = {
	x: number;
	y: number;
	z: number;
	w: number;
};

type Model3dAnimationCallback = (animation: string) => void;

/** Represents the 3D Model object.
 * @see {@link https://www.construct.net/make-games/manuals/construct-3/scripting/scripting-reference/plugin-interfaces/3d-model | I3DModelInstance documentation } */
declare class I3DModelInstance extends IWorldInstance
{
	loadModel(model: string, mesh?: string, animation?: string, playing?: boolean, progress?: number, loop?: boolean): void;

	onLoad(): void;
	onError(): void;

	loadTextureFromURL(uri: string, mesh: string, target: Model3DLoadUrlTargets): Promise<boolean>;
	unloadTextures(model?: string, mesh?: string): Promise<null | undefined>;

	setMeshObject<InstType extends IInstance>(mesh: string, objectClass: IObjectClass<InstType>): void;

	modelName: string;
	meshNames: Array<string>;
	animationName: string;
	animationNames: Array<string>;

	isPlaying: boolean;
	isLooping: boolean;

	isAnimationPlaying(animationName: string): boolean;
	setAnimationPlaying(playing:boolean, animationName: string): void;
	isAnimationLooping(animationName: string): boolean;
	setAnimationLooping(looping:boolean, animationName: string): void;

	animationProgress: number;
	getAnimationProgress(animation: string): number;
	setAnimationProgress(progress: number, animation: string);
	
	getAnimationDuration(animation: string): number;

	meshRenderMode: Model3DRenderModeType;
	backfaceCulling: boolean;
	cullingMode: Model3DCullingModes;
	axisScaleMode: Model3DAxisScaleModeTypes;
	animationBlendMode: Model3DAnimationModeTypes;

	onAnimationFinished: Model3dAnimationCallback;
	onAnimationLooped: Model3dAnimationCallback;

	offsetX: number;
	offsetY: number;
	offsetZ: number;
	rotationX: number;
	rotationY: number;
	rotationZ: number;
	quaternionX: number;
	quaternionY: number;
	quaternionZ: number;
	quaternionW: number;
	scaleX: number;
	scaleY: number;
	scaleZ: number;

	readonly modelX: number;
	readonly modelY: number;
	readonly modelZ: number;
	readonly modelRotationX: number;
	readonly modelRotationY: number;
	readonly modelRotationZ: number;
	readonly modelQuaternionX: number;
	readonly modelQuaternionY: number;
	readonly modelQuaternionZ: number;
	readonly modelQuaternionW: number;
	readonly modelScaleX: number;
	readonly modelScaleY: number;
	readonly modelScaleZ: number;

	setTransform(x: number, y: number, z: number, type: Model3DTransformTypes): void;
	getTransform(type: Model3DTransformTypes, layer: Model3DTransformLayers): Model3DVec3;
	getWorldTransform(type: Model3DTransformTypes): Model3DVec3;
	
	addTransform(x: number, y: number, z: number, type: Model3DTransformTypes): void;
	subTransform(x: number, y: number, z: number, type: Model3DTransformTypes): void;
	mulTransform(x: number, y: number, z: number, type: Model3DTransformTypes): void;
	divTransform(x: number, y: number, z: number, type: Model3DTransformTypes): void;
	resetTransform(type: Model3DResetTransformTypes): void;

	setNodeTransform(nodeType: Model3DNodeTypes, nodeName: string, x: number, y: number, z: number, type: Model3DTransformTypes): void;
	getNodeTransform(nodeType: Model3DNodeTypes, nodeName: string, type: Model3DTransformTypes): Model3DVec3;
	getNodeWorldTransform(nodeType: Model3DNodeTypes, nodeName: string, type: Model3DTransformTypes): Model3DVec3;
	
	addNodeTransform(nodeType: Model3DNodeTypes, nodeName: string, x: number, y: number, z: number, type: Model3DTransformTypes): void;
	subNodeTransform(nodeType: Model3DNodeTypes, nodeName: string, x: number, y: number, z: number, type: Model3DTransformTypes): void;
	mulNodeTransform(nodeType: Model3DNodeTypes, nodeName: string, x: number, y: number, z: number, type: Model3DTransformTypes): void;
	divNodeTransform(nodeType: Model3DNodeTypes, nodeName: string, x: number, y: number, z: number, type: Model3DTransformTypes): void;
	resetNodeTransform(nodeType: Model3DNodeTypes, nodeName: string, type: Model3DResetTransformTypes): void;
	resetAllNodeTransforms(type: Model3DResetTransformTypes): void;

	setModelQuaternion(x: number, y: number, z: number, w: number): void;
	getModelQuaternion(): Model3DQuaternion;
	setNodeQuaternion(nodeType: Model3DNodeTypes, nodeName: string, x: number, y: number, z: number, w: number): void;
	getNodeQuaternion(nodeType: Model3DNodeTypes, nodeName: string): Model3DQuaternion;

	getAllMeshes(): Array<string>;
	getAllAnimations(): Array<string>;

	setMeshEnabled(mesh: string, enable: boolean): void;
	setAllMeshesEnabled(enable: boolean): void;

	isMeshEnabled(mesh: string): boolean;
	areAllMeshesEnabled(): boolean;

	meshExists(mesh: string): boolean;

	play(animationName?: string, progress?: number, transitionDuration?: number, loop?: boolean): void;
	blend(animationName?: string, progress?: number, targetWeight?: number, fadeDuration?: number, loop?: boolean): void;
	stop(): void;
	pause(): void;
	resume(): void;
}