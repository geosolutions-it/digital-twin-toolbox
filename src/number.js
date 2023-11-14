
export const isNumber = value => {
    if (typeof value === 'string') {
        return false;
    }
    const num = parseFloat(value);
    return !isNaN(num);
}
