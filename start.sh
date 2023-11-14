cd /usr/src/app

source activate las

if [ "$DEVELOPMENT" == "true" ]
    then
        npm run start:dev
    else
        npm run start
fi

