"""Canonical aliases retain the actual derivation instead of pretending to be wire fields."""
ALIASES={
 'FIRE':('m_nButtonDownMaskPrev -> demoparser2 FIRE','boolean','network attack state; not physical left mouse or subtick hold proof'),
 'usercmd_buttonstate_1':('CSGOUserCmdPB base.buttons.buttonstate1','bitmask','attack bit 0; availability does not prove complete command decoding'),
 'armor_value':('CCSPlayerPawn.m_ArmorValue','armor points','nonnegative; used only as observed state'),
 'health':('CCSPlayerPawn.m_iHealth','hp','integer [0,100] for this mode'),
 'team_num':('CCSPlayerPawn.m_iTeamNum','enum','2=T,3=CT; others excluded'),
 'pitch':('CCSPlayerPawn.m_angEyeAngles[0]','degrees','[-90,90]; positive downward'),
 'yaw':('CCSPlayerPawn.m_angEyeAngles[1]','degrees','wrap to [-180,180)'),
 'duck_amount':('CCSPlayerPawn.CCSPlayer_MovementServices.m_flDuckAmount','fraction','[0,1]'),
 'is_airborne':('CCSPlayerPawn.m_hGroundEntity -> demoparser2 is_airborne','boolean','derived by parser; optional cross-check m_fFlags'),
 'is_alive':('CCSPlayerPawn.m_lifeState -> demoparser2 is_alive','boolean','parser-derived'),
 'active_weapon_ammo':('Weapon.m_iClip1','rounds','nonnegative; invalid sentinel retained'),
 'accuracy_penalty':('Weapon.m_fAccuracyPenalty','engine scalar','not a movement-only accuracy value'),
 'shots_fired':('CCSPlayerPawn.m_iShotsFired','count','nonnegative; reset may delimit sequences'),
 'flash_duration':('CCSPlayerPawn.m_flFlashDuration','seconds','engine field; conservative exclusion, not reconstructed opacity'),
 'is_scoped':('CCSPlayerPawn.m_bIsScoped','boolean','true/false/NULL'),
 'team_rounds_total':('CCSTeam.m_iScore -> team_rounds_total','rounds','nonnegative'),
 'team_clan_name':('CCSTeam.m_szClanTeamname -> team_clan_name','text','not used as player identity'),
 'is_warmup_period':('CCSGameRulesProxy.CCSGameRules.m_bWarmupPeriod','boolean','unknown is not false'),
 'is_freeze_period':('CCSGameRulesProxy.CCSGameRules.m_bFreezePeriod','boolean','unknown is not false'),
 'total_rounds_played':('CCSGameRulesProxy.CCSGameRules.m_totalRoundsPlayed','rounds','raw counter may reset'),
 'round_win_status':('CCSGameRulesProxy.CCSGameRules.m_iRoundWinStatus','enum','raw engine value'),
 'game_time':('demoparser2 PropType::GameTime (net_tick / 64 in inspected source)','seconds','nonzero origin; validated against FileInfo, never presumed universal'),
 'active_weapon_name':('Weapon item definition index -> demoparser2 weapon mapping','text','NULL when unavailable'),
}
def enrich_catalog(fields,version,tick_seconds):
    for name,spec in fields.items():
        if name in ALIASES:spec.update(raw_path=ALIASES[name][0],unit=ALIASES[name][1],valid_range=ALIASES[name][2])
        elif name in ('X','Y','Z'):
            spec.update(raw_path=f'CCSPlayerPawn.CBodyComponentBaseAnimGraph.m_cell{name} + m_vec{name}',unit='Source units',dependencies=[f'm_cell{name}',f'm_vec{name}'],conversion='demoparser2 cell+offset decoding')
        elif name.startswith('velocity_'):spec.update(unit='Source units/second',raw_path='demoparser2 derived alias:'+name,valid_range='unvalidated timing; not consumed')
        elif name in ('recoil_base','recoil_index','flags','move_type','pawn_handle','weapon_handle','burst_mode','is_reloading'):
            spec.update(unit='degrees[]' if name=='recoil_base' else 'boolean' if name in ('burst_mode','is_reloading') else 'index/bitmask/handle',valid_range='preserve observed type and NULL; no effective-recoil interpretation')
        spec.update(native_resolution_seconds=tick_seconds,observation_interval='previous available demo tick to current tick; event ordering unknown')
    for name,unit,raw,semantics in [('tick','demo tick','command tick observed by adapter','end-of-tick state; not net tick'),('player_id','decimal string','SteamID64','never JavaScript Number'),('demo_time','seconds','tick * FileInfo playback_seconds/playback_ticks','recording tick reference; gaps checked'),('net_tick','tick','not exposed','NULL; not inferred from game_time'),('subtick','seconds','not exposed','NULL; no synthesized fractions')]:
        fields[name]={'canonical_name':name,'raw_path':raw,'unit':unit,'coordinate_convention':None,'type':'string' if name=='player_id' else 'nullable number','source':'adapter','transformation_version':version,'time_semantics':semantics,'valid_range':'NULL on unavailable','null_rule':'never zero-impute','native_resolution_seconds':tick_seconds}
    return fields
