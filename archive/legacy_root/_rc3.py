print('start')
import importlib.util
spec=importlib.util.spec_from_file_location('m','元DGTF-V1.25.0.py')
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
print('loaded')
print(m._auto_pick_route({'fact':True,'short':True,'meta':False,'choice':False,'how':False,'multi':False,'blank':False},{},{'actions':{'all_v2':True},'auto':{'allow_route_trim':True}}))
