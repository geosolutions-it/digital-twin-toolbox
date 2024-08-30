// add this binding to ensure all the streams inside components are working
import '@mapstore/framework/libs/bindings/rxjsRecompose';

import url from 'url';
import main from '@mapstore/framework/product/main';
import pluginsDef from '@js/plugins/def';
import {
    setLocalConfigurationFile,
    setConfigProp
} from '@mapstore/framework/utils/ConfigUtils';
import axios from '@mapstore/framework/libs/ajax';
import MapViewer from '@mapstore/framework/containers/MapViewer';
import { configureMap } from '@mapstore/framework/actions/config';
import { setControlProperty } from '@mapstore/framework/actions/controls';
import security from '@mapstore/framework/reducers/security';
import omit from 'lodash/omit';
import { UPDATE_NODE, changeLayerProperties } from '@mapstore/framework/actions/layers';
import { layersSelector } from '@mapstore/framework/selectors/layers';
import { zoomToExtent } from '@mapstore/framework/actions/map';
import { getCapabilities } from '@mapstore/framework/api/ThreeDTiles';
import { Observable } from 'rxjs';

setLocalConfigurationFile('configs/localConfig.json');
setConfigProp('translationsPath', ['translations', 'ms-translations']);
setConfigProp('extensionsRegistry', 'configs/extensions.json');

// list of path that need version parameter
const pathsNeedVersion = [
    'configs/',
    'assets/',
    'translations/',
    'ms-translations/',
    'print.json'
];

const version = __MAPSTORE_PROJECT_CONFIG__.version || 'dev';

const params = url.parse(window.location.href, true).query || {};

axios.interceptors.request.use(
    config => {
        config.headers.Authorization = `Bearer ${params.access_token}`;
        if (config.url && version && pathsNeedVersion.filter(urlEntry => config.url.match(urlEntry))[0]) {
            return {
                ...config,
                params: {
                    ...config.params,
                    v: version
                }
            };
        }
        return config;
    }
);

const pages = [{
    name: 'home',
    path: '/',
    component: MapViewer
}];

setConfigProp('proxyUrl', false);

document.addEventListener('DOMContentLoaded', function() {
    // example of initial security state
    // with null this state is not initialized
    const user = null;
    const securityState = user && {
        security: {
            user: user,
            token: '' // this token is applied to the request defined in the localConfig authenticationRules properties
        }
    };
    // load a base map configuration
    axios.get( `${params.open_api_base || ''}/api/v1/utils/map`)
        .then(({ data }) => {
            // initialize the mapstore app
            main(
                {
                    targetId: 'container',
                    pages,
                    initialState: {
                        defaultState: {
                            ...securityState
                        }
                    },
                    appReducers: {
                        security
                    },
                    appEpics: {
                        dttZoomToTileset: (action$, store) => action$.ofType(UPDATE_NODE)
                            .filter(action => action?.options?.visibility === true)
                            .switchMap((action) => {
                                const layers = layersSelector(store.getState());
                                const layer = layers.find((l) => l.id === action.node);
                                if (layer.type !== '3dtiles') {
                                    return Observable.empty();
                                }
                                if (layer.bbox) {
                                    return Observable.of(zoomToExtent(layer.bbox.bounds, layer.bbox.crs));
                                }
                                return Observable.defer(() => getCapabilities(layer.url))
                                    .switchMap(({ bbox, format }) => {
                                        return Observable.of(
                                            zoomToExtent(bbox.bounds, bbox.crs),
                                            changeLayerProperties(layer.id, { bbox, format })
                                        );
                                    });
                            })
                    },
                    printingEnabled: false
                },
                pluginsDef,
                // TODO: use default main import to avoid override
                (cfg) => ({
                    ...cfg,
                    // remove epics that manage the map type for the standard product
                    appEpics: omit(cfg.appEpics, [
                        'syncMapType',
                        'updateLast2dMapTypeOnChangeEvents',
                        'restore2DMapTypeOnLocationChange'
                    ]),
                    initialActions: [
                        setControlProperty.bind(null, 'toolbar', 'expanded', false),
                        configureMap.bind(null, data, 1, true)
                    ]
                }));
        });
});
