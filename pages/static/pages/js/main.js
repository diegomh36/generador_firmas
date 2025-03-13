
//Funcion para cambiar el formulario segun la seleccion, hay que cambiar
async function changeDivs(){
    let reductionBy = reductionByElement.value
    let goalBy = goalByElement.value
    let startWeight = 0

    if (goalBy == byPercentage) {
        $('#div_goal_weight').parent().removeClass('d-none')
        $('#div_id_goal_value').parent().addClass('d-none')
        $('#div_id_reduction_goal').parent().removeClass('d-none')
        $('#div_goal_measurement').parent().addClass('d-none')
        //$('#div_id_starting_value').parent().addClass('d-none')
        if (reductionBy== byCenterProductionRatio && hasPeopleCounterData){
            $('#div_id_use_people_counter_data').parent().parent().removeClass('d-none')
        } else if(reductionBy == byWeight){
            $('#div_id_use_people_counter_data').parent().parent().addClass('d-none')
        }
    } else {
        $('#div_id_goal_value').parent().removeClass('d-none')
        $('#div_goal_weight').parent().addClass('d-none')
        $('#div_id_reduction_goal').parent().addClass('d-none')
        $('#div_goal_measurement').parent().removeClass('d-none')
        if (reductionBy== byCenterProductionRatio){
            document.getElementById('id_goal_measurement').value = 'Gramos'
            if (hasPeopleCounterData){
                $('#div_id_use_people_counter_data').parent().parent().removeClass('d-none')
            }
        } else if(reductionBy == byWeight){
            document.getElementById('id_goal_measurement').value = 'Gramos'
            $('#div_id_use_people_counter_data').parent().parent().addClass('d-none')
        }
    }
    changeDateCallback()
}