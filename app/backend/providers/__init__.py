from pathlib import Path
import json, math

class MapGeometryProvider:
    version='none'
    def raycast(self,map_name,start,end): return {'visible':None,'reason':'未安装匹配地图的碰撞与烟雾资源'}
    def anchors(self,map_name): return None

class VisibilityProvider:
    version='unknown-1'
    def __init__(self,geometry): self.geometry=geometry
    def query(self,map_name,eye,head,tick): return self.geometry.raycast(map_name,eye,head)

class PlayerGeometryProvider:
    version='linear-pose-experiment-1'
    def points(self,s,params):
        duck=s.get('duck_amount')
        if duck is None or not math.isfinite(float(duck)) or not 0<=duck<=1: return None
        z=float(s['Z']); d=float(duck)
        eye=z+params['eye_stand']*(1-d)+params['eye_duck']*d
        head=z+params['head_stand']*(1-d)+params['head_duck']*d
        return (float(s['X']),float(s['Y']),eye),(float(s['X']),float(s['Y']),head)

class WeaponProfiles:
    version='reference-speed-34pct-2'
    def __init__(self): self.data=json.loads((Path(__file__).parent/'weapons.json').read_text())
    def normalize(self,name):
        name=(name or '').lower().replace('weapon_','')
        return self.data['aliases'].get(name,name)
    def get(self,name,scoped=False,duck=0):
        name=self.normalize(name)
        p=self.data['profiles'].get(name)
        if not p: return None
        zoom_weapon=name in ('awp','ssg08','g3sg1','scar20','aug','sg556')
        speed=None if zoom_weapon and scoped is None else p['scoped_max_speed'] if zoom_weapon and scoped else p['max_speed']
        return {**p,'weapon':name,'selected_max_speed':speed,'threshold':speed*.34 if speed is not None else None,
                'quality':'estimated','source':'武器数据快照 × 34% 参考规则；非全精度保证，未按 demo 补丁标定',
                'data_source':self.data['source'],'version':self.version}

    def in_weapon_set(self,name,weapon_set):
        p=self.get(name)
        if not p:return False
        return weapon_set=='all' or (p['group'] not in ('smg','shotgun') and (p['group']!='pistol' or p['weapon']=='deagle'))

class Providers:
    def __init__(self,meta):
        self.map=MapGeometryProvider(); self.visibility=VisibilityProvider(self.map)
        self.geometry=PlayerGeometryProvider(); self.weapons=WeaponProfiles()
        self.identities={'map':self.map.version,'visibility':self.visibility.version,'geometry':self.geometry.version,'weapons':self.weapons.version}
