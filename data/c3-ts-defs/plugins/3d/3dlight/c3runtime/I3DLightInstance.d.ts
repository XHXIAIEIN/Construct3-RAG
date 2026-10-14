
type Light3DLightType = "point" | "directional" | "spot";

/** Represents the 3D Light object.
 * @see {@link https://www.construct.net/make-games/manuals/construct-3/scripting/scripting-reference/plugin-interfaces/3d-light | I3DLightInstance documentation } */
declare class I3DLightInstance extends IWorldInstance
{
	lightType: Light3DLightType;
	intensity: number;
	referenceDistance: number;
	attenuationFactor: number;
	radius: number;
	innerAngle: number;
	outerAngle: number;
}
