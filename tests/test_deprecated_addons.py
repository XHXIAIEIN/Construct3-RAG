"""Addon deprecation read from the editor bundles, on minified code shaped
like the real main.js, allEditorPlugins.js and allEditorBehaviors.js."""
import pytest

from src.ingest.deprecated_addons import deprecated_ids, deprecated_setter, extract_deprecation

# The public classes call a minified setter; each kind has its own, and the
# names change from one build to the next (Fs in r495.2, Fe in r503).
MAIN_JS = (
    'var q;window.SDK.IPluginInfo=class{constructor(t){Ak.set(this,t)}SetIsTiled(t){Ak.get(this).cT(t)}'
    'SetIsDeprecated(t){Ak.get(this).Fs(t)}SetIsSingleGlobal(t){Ak.get(this).it(t)}};'
    'window.SDK.IBehaviorInfo=class{SetIsOnlyOneAllowed(t){$k.get(this).cV(t)}'
    'SetIsDeprecated(t){$k.get(this).Gq(t)}};'
)

PLUGINS_JS = (
    # A setter call inside a property callback is not the constructor's own.
    '{const a=self.t,b=self.lang,c="Sprite",d=a.h.S=class extends a.l{constructor(){super(),'
    'a.u.o("plugins."+c.toLowerCase()),this.p=a.m(self.v,c),this.p.k(b(".name")),'
    'this.p.gi([new a.P("x",{callback:()=>this.p.Fs(!0)})]),a.u.et()}}}'
    '{const e=self.t,f="NodeWebkit",g=e.h.N=class extends e.l{constructor(){super(),'
    'this.p=e.m(self.v,f),this.p.it(!0),this.p.Fs(!0),e.u.et()}}}'
    # const t=this.p=...: the calls go through the alias.
    '{const h=self.t,i="Keyboard";h.h.K=class extends h.l{constructor(){super();'
    'const t=this.p=h.m(self.v,i);t.k("x"),t.Fs(!1)}}}'
    '{const j=self.t,k="Function";j.h.F=class extends j.l{constructor(){super();'
    'const t=this.p=j.m(self.v,k);t.k("x"),t.Fs(!0)}}}'
)

BEHAVIORS_JS = (
    '{const a=self.t,b="Pin";a.tV.P=class extends a.iV{constructor(){super(),'
    'this.p=a.m(self.sV,b),this.p.k("x"),this.p.Fs(!0)}}}'
    '{const c=self.t,d="Retired";c.tV.R=class extends c.iV{constructor(){super(),'
    'this.p=c.m(self.sV,d),this.p.Gq(!0)}}}'
)


def test_setter_is_resolved_per_kind_from_the_sdk_class():
    assert deprecated_setter(MAIN_JS, "plugins") == "Fs"
    assert deprecated_setter(MAIN_JS, "behaviors") == "Gq"


def test_constructor_calls_decide_and_callbacks_do_not():
    assert extract_deprecation(MAIN_JS, PLUGINS_JS, "plugins") == {
        "Sprite": False, "NodeWebkit": True, "Keyboard": False, "Function": True,
    }


def test_a_behavior_is_read_with_the_behavior_setter():
    # Pin calls the plugin class's setter name, which means nothing on a behavior.
    assert extract_deprecation(MAIN_JS, BEHAVIORS_JS, "behaviors") == {"Pin": False, "Retired": True}


def test_the_info_and_its_factory_are_read_under_their_names_of_the_build():
    # r506 builds the info as const l=this.m=e.v(self.k,s), and a method may
    # assign through the same shape to another property: the constructors'
    # pair is the one most of them share.
    renamed = PLUGINS_JS.replace("this.p", "this.m").replace(".m(self.v,", ".v(self.k,")
    stray = '{const z=self.t;z.h.X=class{mn(){this.rn=z.v(self.xn,this),this.rn.Fs(!0)}}}'
    assert extract_deprecation(MAIN_JS, renamed + stray, "plugins") == {
        "Sprite": False, "NodeWebkit": True, "Keyboard": False, "Function": True,
    }


# Excerpts of the r506 bundles, shortened. r506 builds the info as
# this.m=X.v(self.Ji,ID), while X.p is another object of the bundle, so the
# r495 shape this.p=X.m(self.v,ID) matches nothing there and stops the read.
R506_MAIN_JS = (
    'window.SDK.IPluginInfo=class{SetIsTiled(t){Ck.get(this).NV(t)}SetIsDeprecated(t){Ck.get(this).pr(t)}};'
    'window.SDK.IBehaviorInfo=class{SetIsOnlyOneAllowed(t){Fk.get(this).ve(t)}'
    'SetIsDeprecated(t){Fk.get(this).pr(t)}};'
)
R506_PLUGINS_JS = (
    '{const $o=self.t,Qo=self.lang,Xo="NodeWebkit",Zo=$o.Hi.Aw=class extends $o.qi{constructor(){super(),'
    '$o.p.dr(!1),$o.p.u("plugins."+Xo.toLowerCase()),this.m=$o.v(self.Ji,Xo),this.m.j(Qo(".name")),'
    'this.m.$i(!0),this.m.pr(!0),$o.p.re(),$o.p.dr(!0)}}}'
    '{const yr=self.t,xr=self.lang,Sr="Keyboard",Cr=yr.Hi.Keyboard=class extends yr.qi{constructor(){super(),'
    'yr.p.u("plugins.keyboard");const t=this.m=yr.v(self.Ji,Sr);t.j(xr(".name")),t.$i(!0),yr.p.re()}}}'
)
R506_BEHAVIORS_JS = (
    '{const ts=self.t,is=self.lang,ss="Pin",ls=ts.o.Kt=class extends ts.h{constructor(){super(),'
    'ts.p.u("behaviors."+ss.toLowerCase()),this.m=ts.v(self.k,ss),this.m.j(is(".name"))}}}'
)


def test_the_r506_bundles_are_read():
    assert extract_deprecation(R506_MAIN_JS, R506_PLUGINS_JS, "plugins") == {"NodeWebkit": True, "Keyboard": False}
    assert extract_deprecation(R506_MAIN_JS, R506_BEHAVIORS_JS, "behaviors") == {"Pin": False}


def test_deprecated_ids_stops_on_an_addon_the_bundle_does_not_construct():
    flags = extract_deprecation(MAIN_JS, PLUGINS_JS, "plugins")
    assert deprecated_ids(flags, {"Sprite", "NodeWebkit"}, "plugins") == {"NodeWebkit"}
    with pytest.raises(ValueError, match="plugin Tilemap"):
        deprecated_ids(flags, {"Sprite", "Tilemap"}, "plugins")


def test_a_bundle_of_another_shape_stops_the_read():
    with pytest.raises(ValueError, match="IBehaviorInfo"):
        deprecated_setter(MAIN_JS.split("window.SDK.IBehaviorInfo")[0], "behaviors")
    with pytest.raises(ValueError, match="no plugin constructor"):
        extract_deprecation(MAIN_JS, PLUGINS_JS.replace("(self.v,", "(0,"), "plugins")
    with pytest.raises(ValueError, match="calls SetIsDeprecated with"):
        extract_deprecation(MAIN_JS, PLUGINS_JS.replace("t.Fs(!0)", 't.Fs("yes")'), "plugins")
