import { compileExpression } from 'filtrex';
import { isNumber } from './number.js';

export const parseNumericExpression = (value, properties) => {
    if (!value) {
        return undefined;
    }
    try {
        const result = compileExpression(value)({ ...properties });
        return isNumber(result) ? result : undefined;
    } catch (e) {
        return undefined;
    }
};

export const parseStringExpression = (value, properties) => {
    if (!value) {
        return undefined;
    }
    try {
        const result = compileExpression(value)({ ...properties });
        return `${result}`;
    } catch (e) {
        return undefined;
    }
};
